import os
import uuid
import json
import logging
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g, send_file, abort, jsonify,
)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from database import get_db, close_db, init_db
from ai_screening import screen_application
from email_service import init_mail, send_verification_email

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True

CORS(app, origins=["http://localhost:5173", "http://127.0.0.1:5173", "https://entr.up.railway.app"], supports_credentials=True)
init_mail(app)

# Verification uploads stored OUTSIDE static/ so they are never web-accessible
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "verification")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file, prefix: str, user_id: int) -> str:
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{prefix}_{user_id}_{uuid.uuid4().hex[:10]}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    return filepath


def row_to_dict(row):
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return None
    return dict(row)


@app.teardown_appcontext
def teardown_db(e=None):
    close_db()


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_verification(worker_id: int):
    return get_db().execute(
        "SELECT * FROM verifications WHERE worker_id = ?", (worker_id,)
    ).fetchone()


def login_required(role=None):
    def decorator(f):
        from functools import wraps

        @wraps(f)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if not user:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login"))
            if role and user["role"] != role:
                flash("Access denied.", "error")
                return redirect(url_for("index"))
            return f(*args, **kwargs)

        return wrapped

    return decorator


def api_login_required(role=None):
    """Decorator for API routes — returns JSON errors instead of redirects."""
    def decorator(f):
        from functools import wraps

        @wraps(f)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({'error': 'Authentication required'}), 401
            if role and user["role"] != role:
                return jsonify({'error': 'Access denied'}), 403
            return f(*args, **kwargs)

        return wrapped

    return decorator


# ── Public routes ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    user = get_current_user()
    if user:
        if user["role"] == "employer":
            return redirect(url_for("employer_dashboard"))
        return redirect(url_for("worker_dashboard"))
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        name     = request.form.get("name", "").strip()
        role     = request.form.get("role", "")
        language_pref   = request.form.get("language_pref", "en")
        restaurant_name = request.form.get("restaurant_name", "").strip()
        phone           = request.form.get("phone", "").strip()

        if not all([email, password, name, role]):
            flash("Please fill in all required fields.", "error")
            return render_template("signup.html")

        if role not in ("employer", "worker"):
            flash("Invalid role selected.", "error")
            return render_template("signup.html")

        db = get_db()
        if db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            flash("An account with that email already exists.", "error")
            return render_template("signup.html")

        pw_hash = generate_password_hash(password)
        db.execute(
            """INSERT INTO users
               (email, password_hash, role, name, phone, language_pref, restaurant_name)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (email, pw_hash, role, name, phone, language_pref, restaurant_name),
        )
        db.commit()

        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        session["user_id"] = user["id"]
        session["lang"]    = language_pref

        if role == "employer":
            return redirect(url_for("employer_dashboard"))
        # Workers go to verify before browsing
        return redirect(url_for("worker_verify"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db   = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["lang"]    = user["language_pref"]

        if user["role"] == "employer":
            return redirect(url_for("employer_dashboard"))
        return redirect(url_for("worker_dashboard"))

    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user:
            import secrets as _secrets
            import datetime as _datetime

            token = _secrets.token_urlsafe(32)
            expiry = _datetime.datetime.utcnow() + _datetime.timedelta(hours=1)

            db.execute(
                "UPDATE users SET password_reset_token = ?, password_reset_expiry = ? WHERE id = ?",
                (token, expiry, user["id"]),
            )
            db.commit()

            from email_service import send_password_reset_email
            send_password_reset_email(email, user["name"], token, user["language_pref"])

        flash("Check your email for password reset instructions.", "info")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    token = request.args.get("token", "").strip()

    if request.method == "POST":
        token = request.form.get("token", "").strip()
        new_password = request.form.get("new_password", "").strip()

        if not new_password or len(new_password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("reset_password.html", token=token)

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE password_reset_token = ? AND password_reset_expiry > datetime('now')",
            (token,),
        ).fetchone()

        if not user:
            flash("Invalid or expired reset link.", "error")
            return redirect(url_for("login"))

        pw_hash = generate_password_hash(new_password)
        db.execute(
            "UPDATE users SET password_hash = ?, password_reset_token = NULL, password_reset_expiry = NULL WHERE id = ?",
            (pw_hash, user["id"]),
        )
        db.commit()

        flash("Password reset successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/set-language/<lang>")
def set_language(lang):
    if lang in ("en", "es", "zh", "fr", "pt", "vi"):
        session["lang"] = lang
        user = get_current_user()
        if user:
            db = get_db()
            db.execute("UPDATE users SET language_pref = ? WHERE id = ?", (lang, user["id"]))
            db.commit()
    return redirect(request.referrer or url_for("index"))


# ── Employer routes ───────────────────────────────────────────────────────────

@app.route("/employer/dashboard")
@login_required(role="employer")
def employer_dashboard():
    user = get_current_user()
    db   = get_db()
    jobs = db.execute(
        """SELECT j.*, COUNT(a.id) as application_count
           FROM jobs j
           LEFT JOIN applications a ON a.job_id = j.id
           WHERE j.employer_id = ?
           GROUP BY j.id
           ORDER BY j.created_at DESC""",
        (user["id"],),
    ).fetchall()
    return render_template("employer/dashboard.html", user=user, jobs=jobs)


@app.route("/employer/post-job", methods=["GET", "POST"])
@login_required(role="employer")
def post_job():
    user = get_current_user()
    if request.method == "POST":
        title       = request.form.get("title", "").strip()
        pay         = request.form.get("pay", "").strip()
        hours       = request.form.get("hours", "").strip()
        exp         = int(request.form.get("experience_required", 0))
        lang_pref   = request.form.get("language_preference", "").strip()
        location    = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()

        if not all([title, pay, hours]):
            flash("Position, pay, and hours are required.", "error")
            return render_template("employer/post_job.html", user=user)

        import datetime as _datetime
        expires_at = _datetime.datetime.utcnow() + _datetime.timedelta(days=30)

        db = get_db()
        db.execute(
            """INSERT INTO jobs
               (employer_id, title, pay, hours, experience_required,
                language_preference, location, description, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user["id"], title, pay, hours, exp, lang_pref, location, description, expires_at),
        )
        db.commit()
        flash("Job posted successfully!", "success")
        return redirect(url_for("employer_dashboard"))

    return render_template("employer/post_job.html", user=user)


@app.route("/employer/jobs/<int:job_id>/toggle", methods=["POST"])
@login_required(role="employer")
def toggle_job(job_id):
    user = get_current_user()
    db   = get_db()
    job  = db.execute(
        "SELECT * FROM jobs WHERE id = ? AND employer_id = ?", (job_id, user["id"])
    ).fetchone()
    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("employer_dashboard"))
    new_status = "closed" if job["status"] == "open" else "open"
    db.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, job_id))
    db.commit()
    return redirect(url_for("employer_dashboard"))


@app.route("/employer/jobs/<int:job_id>/applications")
@login_required(role="employer")
def view_applications(job_id):
    user = get_current_user()
    db   = get_db()
    job  = db.execute(
        "SELECT * FROM jobs WHERE id = ? AND employer_id = ?", (job_id, user["id"])
    ).fetchone()
    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("employer_dashboard"))

    applications = db.execute(
        """SELECT a.*,
                  u.name, u.email, u.phone, u.bio, u.experience_years, u.languages_spoken,
                  v.verification_status, v.age_verified,
                  v.face_match_score,    v.extracted_name,
                  v.extracted_dob,       v.id AS verification_id
           FROM applications a
           JOIN users u ON u.id = a.worker_id
           LEFT JOIN verifications v ON v.worker_id = a.worker_id
           WHERE a.job_id = ?
           ORDER BY a.ai_score DESC, a.created_at DESC""",
        (job_id,),
    ).fetchall()

    return render_template(
        "employer/applications.html",
        user=user, job=job, applications=applications,
    )


@app.route("/employer/applications/<int:app_id>/status", methods=["POST"])
@login_required(role="employer")
def update_application_status(app_id):
    user       = get_current_user()
    new_status = request.form.get("status")
    if new_status not in ("pending", "reviewed", "accepted", "rejected"):
        flash("Invalid status.", "error")
        return redirect(request.referrer or url_for("employer_dashboard"))

    db      = get_db()
    app_row = db.execute(
        """SELECT a.*, j.employer_id FROM applications a
           JOIN jobs j ON j.id = a.job_id WHERE a.id = ?""",
        (app_id,),
    ).fetchone()

    if not app_row or app_row["employer_id"] != user["id"]:
        flash("Application not found.", "error")
        return redirect(url_for("employer_dashboard"))

    db.execute("UPDATE applications SET status = ? WHERE id = ?", (new_status, app_id))
    db.commit()
    return redirect(request.referrer or url_for("employer_dashboard"))


@app.route("/employer/applications/<int:app_id>/verification")
@login_required(role="employer")
def view_verification_detail(app_id):
    """Employer view of a worker's verification summary (no ID images shown)."""
    user    = get_current_user()
    db      = get_db()
    app_row = db.execute(
        """SELECT a.*, j.employer_id, u.name AS worker_name, u.email AS worker_email
           FROM applications a
           JOIN jobs j ON j.id = a.job_id
           JOIN users u ON u.id = a.worker_id
           WHERE a.id = ?""",
        (app_id,),
    ).fetchone()

    if not app_row or app_row["employer_id"] != user["id"]:
        flash("Application not found.", "error")
        return redirect(url_for("employer_dashboard"))

    verification = get_verification(app_row["worker_id"])
    return render_template(
        "employer/verification_detail.html",
        user=user, app=app_row, verification=verification,
    )


# ── Worker routes ─────────────────────────────────────────────────────────────

@app.route("/worker/dashboard")
@login_required(role="worker")
def worker_dashboard():
    user = get_current_user()
    db   = get_db()
    my_applications = db.execute(
        """SELECT a.*, j.title, j.pay, j.hours, j.location,
                  u.name AS employer_name, u.restaurant_name
           FROM applications a
           JOIN jobs j ON j.id = a.job_id
           JOIN users u ON u.id = j.employer_id
           WHERE a.worker_id = ?
           ORDER BY a.created_at DESC""",
        (user["id"],),
    ).fetchall()
    verification = get_verification(user["id"])
    return render_template(
        "worker/dashboard.html",
        user=user, applications=my_applications, verification=verification,
    )


@app.route("/worker/profile", methods=["GET", "POST"])
@login_required(role="worker")
def worker_profile():
    user = get_current_user()
    if request.method == "POST":
        bio                = request.form.get("bio", "").strip()
        experience_years   = int(request.form.get("experience_years", 0))
        languages_spoken   = request.form.get("languages_spoken", "").strip()
        phone              = request.form.get("phone", "").strip()
        skills             = request.form.get("skills", "").strip()
        availability       = request.form.get("availability", "").strip()
        dialect_preference = request.form.get("dialect_preference", "").strip()

        db = get_db()
        db.execute(
            """UPDATE users
               SET bio=?, experience_years=?, languages_spoken=?, phone=?,
                   skills=?, availability=?, dialect_preference=?
               WHERE id=?""",
            (bio, experience_years, languages_spoken, phone, skills, availability, dialect_preference, user["id"]),
        )
        db.commit()
        flash("Profile updated!", "success")
        return redirect(url_for("worker_profile"))

    verification = get_verification(user["id"])
    return render_template("worker/profile.html", user=user, verification=verification)


@app.route("/worker/applications/<int:app_id>/set-availability", methods=["GET", "POST"])
@login_required(role="worker")
def set_interview_availability(app_id):
    """Worker sets their availability for interviews."""
    user = get_current_user()
    db   = get_db()

    app = db.execute(
        "SELECT a.*, j.title FROM applications a JOIN jobs j ON j.id = a.job_id WHERE a.id = ? AND a.worker_id = ?",
        (app_id, user["id"]),
    ).fetchone()
    if not app:
        flash("Application not found.", "error")
        return redirect(url_for("worker_dashboard"))

    if request.method == "POST":
        days = request.form.getlist("days")
        times = request.form.getlist("times")

        if not days or not times:
            flash("Please select at least one day and one time.", "error")
            return render_template("worker/set_availability.html", user=user, app=app)

        availability_data = {"days": days, "times": times}
        db.execute(
            "UPDATE applications SET worker_availability = ? WHERE id = ?",
            (json.dumps(availability_data), app_id),
        )
        db.commit()
        flash("Availability saved! Employers can now schedule interviews.", "success")
        return redirect(url_for("worker_dashboard"))

    return render_template("worker/set_availability.html", user=user, app=app)


@app.route("/worker/jobs")
@login_required(role="worker")
def browse_jobs():
    user = get_current_user()
    db   = get_db()
    applied_ids = {
        row["job_id"]
        for row in db.execute(
            "SELECT job_id FROM applications WHERE worker_id = ?", (user["id"],)
        ).fetchall()
    }
    jobs = db.execute(
        """SELECT j.*, u.name AS employer_name, u.restaurant_name
           FROM jobs j JOIN users u ON u.id = j.employer_id
           WHERE j.status = 'open'
           ORDER BY j.created_at DESC""",
    ).fetchall()
    verification = get_verification(user["id"])
    return render_template(
        "worker/browse_jobs.html",
        user=user, jobs=jobs, applied_ids=applied_ids, verification=verification,
    )


@app.route("/worker/jobs/<int:job_id>/apply", methods=["GET", "POST"])
@login_required(role="worker")
def apply_job(job_id):
    user = get_current_user()
    db   = get_db()

    job = db.execute(
        """SELECT j.*, u.name AS employer_name, u.restaurant_name
           FROM jobs j JOIN users u ON u.id = j.employer_id
           WHERE j.id = ? AND j.status = 'open'""",
        (job_id,),
    ).fetchone()
    if not job:
        flash("This job is no longer available.", "error")
        return redirect(url_for("browse_jobs"))

    if db.execute(
        "SELECT id FROM applications WHERE job_id=? AND worker_id=?", (job_id, user["id"])
    ).fetchone():
        flash("You have already applied to this job.", "error")
        return redirect(url_for("browse_jobs"))

    if request.method == "POST":
        cover_letter = request.form.get("cover_letter", "").strip()
        verification = get_verification(user["id"])
        vstatus      = verification["verification_status"] if verification else None

        score, summary = screen_application(dict(job), dict(user), cover_letter, vstatus)

        db.execute(
            """INSERT INTO applications (job_id, worker_id, cover_letter, ai_score, ai_summary)
               VALUES (?, ?, ?, ?, ?)""",
            (job_id, user["id"], cover_letter, score, summary),
        )
        db.commit()
        app_id = db.execute(
            "SELECT id FROM applications WHERE job_id=? AND worker_id=?", (job_id, user["id"])
        ).fetchone()["id"]
        return redirect(url_for("set_interview_availability", app_id=app_id))

    return render_template("worker/apply.html", user=user, job=job)


# ── Worker verification routes ────────────────────────────────────────────────

@app.route("/worker/verify", methods=["GET"])
@login_required(role="worker")
def worker_verify():
    user         = get_current_user()
    verification = get_verification(user["id"])

    step = 1
    if verification:
        if verification["id_document_path"]:
            step = 2
        if verification["selfie_path"]:
            step = 3

    return render_template(
        "worker/verify.html",
        user=user, verification=verification, step=step,
    )


@app.route("/worker/verify/upload-id", methods=["POST"])
@login_required(role="worker")
def upload_id_document():
    user = get_current_user()
    db   = get_db()

    f = request.files.get("id_document")
    if not f or not f.filename or not allowed_file(f.filename):
        flash("Please upload a JPG or PNG image of your ID.", "error")
        return redirect(url_for("worker_verify"))

    filepath = save_upload(f, "id", user["id"])

    existing = db.execute(
        "SELECT id FROM verifications WHERE worker_id=?", (user["id"],)
    ).fetchone()
    if existing:
        db.execute(
            """UPDATE verifications
               SET id_document_path=?, selfie_path=NULL,
                   verification_status='pending', failure_reason=NULL,
                   face_match_score=NULL, identity_verified=0,
                   extracted_name=NULL, extracted_dob=NULL, verified_at=NULL
               WHERE worker_id=?""",
            (filepath, user["id"]),
        )
    else:
        db.execute(
            "INSERT INTO verifications (worker_id, id_document_path) VALUES (?,?)",
            (user["id"], filepath),
        )
    db.commit()

    flash("ID uploaded. Now upload a selfie to complete verification.", "success")
    return redirect(url_for("worker_verify"))


@app.route("/worker/verify/upload-selfie", methods=["POST"])
@login_required(role="worker")
def upload_selfie():
    user         = get_current_user()
    db           = get_db()
    verification = get_verification(user["id"])

    if not verification or not verification["id_document_path"]:
        flash("Please upload your ID document first.", "error")
        return redirect(url_for("worker_verify"))

    f = request.files.get("selfie")
    if not f or not f.filename or not allowed_file(f.filename):
        flash("Please upload a JPG or PNG selfie.", "error")
        return redirect(url_for("worker_verify"))

    filepath = save_upload(f, "selfie", user["id"])
    db.execute("UPDATE verifications SET selfie_path=? WHERE worker_id=?", (filepath, user["id"]))
    db.commit()

    # Run the verification pipeline
    from ai_verification import run_verification
    try:
        result = run_verification(
            user["id"],
            verification["id_document_path"],
            filepath,
            db,
        )
        if result["verification_status"] == "verified":
            flash("Identity verified. You can now apply to jobs.", "success")
        elif result["verification_status"] == "flagged":
            flash(result["failure_reason"], "error")
        else:
            flash("Verification submitted and is being reviewed by our team.", "success")
    except Exception as e:
        db.execute(
            "UPDATE verifications SET failure_reason=? WHERE worker_id=?",
            ("Processing error — queued for manual review.", user["id"]),
        )
        db.commit()
        flash("Verification submitted and will be reviewed shortly.", "success")

    return redirect(url_for("worker_verify"))


@app.route("/worker/verify/resubmit", methods=["POST"])
@login_required(role="worker")
def resubmit_verification():
    """Reset verification so the worker can start over."""
    user = get_current_user()
    db   = get_db()
    db.execute(
        """UPDATE verifications
           SET id_document_path=NULL, selfie_path=NULL,
               verification_status='pending', failure_reason=NULL,
               face_match_score=NULL, identity_verified=0, age_verified=0,
               extracted_name=NULL, extracted_dob=NULL, verified_at=NULL
           WHERE worker_id=?""",
        (user["id"],),
    )
    db.commit()
    return redirect(url_for("worker_verify"))


# ── Secure image serving ──────────────────────────────────────────────────────

@app.route("/verification/image/<int:verification_id>/<image_type>")
@login_required()
def serve_verification_image(verification_id, image_type):
    """
    Serve ID / selfie images only to the worker who owns the record.
    Employers never receive the raw documents.
    """
    user         = get_current_user()
    db           = get_db()
    verification = db.execute(
        "SELECT * FROM verifications WHERE id=?", (verification_id,)
    ).fetchone()

    if not verification:
        abort(404)
    if verification["worker_id"] != user["id"]:
        abort(403)

    path = verification["id_document_path"] if image_type == "id" else (
           verification["selfie_path"]        if image_type == "selfie" else None)

    if not path or not os.path.exists(path):
        abort(404)

    return send_file(path)


# ── JSON API routes ───────────────────────────────────────────────────────────

# Auth

@app.route("/api/auth/me")
def api_auth_me():
    user = get_current_user()
    if not user:
        return jsonify({'user': None}), 200
    u = row_to_dict(user)
    u.pop('password_hash', None)
    u.pop('email_verification_token', None)
    return jsonify({'user': u}), 200


@app.route("/api/auth/validate-session", methods=["POST"])
def api_auth_validate_session():
    """
    Validate the current session. Frontend can call this on page load to ensure
    the localStorage session is still valid on the backend.
    Returns 200 with user data if valid, 401 if invalid/expired.
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Session invalid or expired', 'valid': False}), 401
    u = row_to_dict(user)
    u.pop('password_hash', None)
    u.pop('email_verification_token', None)
    return jsonify({'valid': True, 'user': u}), 200


@app.route("/api/auth/signup", methods=["POST"])
def api_auth_signup():
    data = request.get_json(force=True)
    email           = (data.get("email") or "").strip().lower()
    password        = data.get("password") or ""
    name            = (data.get("name") or "").strip()
    role            = data.get("role") or ""
    language_pref   = data.get("language_pref") or "en"
    restaurant_name = (data.get("restaurant_name") or "").strip()
    phone           = (data.get("phone") or "").strip()

    if not all([email, password, name, role]):
        return jsonify({'error': 'Please fill in all required fields'}), 400

    if role not in ("employer", "worker"):
        return jsonify({'error': 'Invalid role'}), 400

    db = get_db()
    if db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
        return jsonify({'error': 'An account with that email already exists'}), 409

    import secrets as _secrets
    token   = _secrets.token_urlsafe(32)
    pw_hash = generate_password_hash(password)
    db.execute(
        """INSERT INTO users
           (email, password_hash, role, name, phone, language_pref, restaurant_name,
            email_verified, email_verification_token)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
        (email, pw_hash, role, name, phone, language_pref, restaurant_name, token),
    )
    db.commit()

    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    session["user_id"] = user["id"]
    session["lang"]    = language_pref

    # Send verification email (non-blocking; logs to console if SMTP not configured)
    sent = send_verification_email(email, name, token)

    u = row_to_dict(user)
    u.pop('password_hash', None)
    u.pop('email_verification_token', None)
    return jsonify({'user': u, 'verification_email_sent': sent}), 201


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    data     = request.get_json(force=True)
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({'error': 'Invalid email or password'}), 401

    session["user_id"] = user["id"]
    session["lang"]    = user["language_pref"]

    u = row_to_dict(user)
    u.pop('password_hash', None)
    u.pop('email_verification_token', None)
    return jsonify({'user': u})


@app.route("/api/auth/verify-email", methods=["POST"])
def api_verify_email():
    data  = request.get_json(force=True)
    token = (data.get("token") or "").strip()
    if not token:
        return jsonify({"error": "Verification token is required."}), 400

    db   = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE email_verification_token = ?", (token,)
    ).fetchone()
    if not user:
        return jsonify({"error": "This link is invalid or has already been used."}), 400

    db.execute(
        "UPDATE users SET email_verified = 1, email_verification_token = NULL WHERE id = ?",
        (user["id"],),
    )
    db.commit()
    return jsonify({"ok": True, "role": user["role"]})


@app.route("/api/auth/resend-verification", methods=["POST"])
@api_login_required()
def api_resend_verification():
    import secrets as _secrets
    user = get_current_user()
    if user["email_verified"]:
        return jsonify({"error": "Email is already verified."}), 400

    token = _secrets.token_urlsafe(32)
    get_db().execute(
        "UPDATE users SET email_verification_token = ? WHERE id = ?", (token, user["id"])
    )
    get_db().commit()
    sent = send_verification_email(user["email"], user["name"], token)
    return jsonify({"ok": True, "sent": sent})


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    session.clear()
    return jsonify({'ok': True})


# Employer API

@app.route("/api/employer/jobs")
@api_login_required(role="employer")
def api_employer_jobs():
    user = get_current_user()
    db   = get_db()
    jobs = db.execute(
        """SELECT j.*, COUNT(a.id) as application_count
           FROM jobs j
           LEFT JOIN applications a ON a.job_id = j.id
           WHERE j.employer_id = ?
           GROUP BY j.id
           ORDER BY j.created_at DESC""",
        (user["id"],),
    ).fetchall()
    return jsonify({'jobs': [row_to_dict(j) for j in jobs]})


@app.route("/api/employer/jobs", methods=["POST"])
@api_login_required(role="employer")
def api_employer_create_job():
    user = get_current_user()
    data = request.get_json(force=True)

    title       = (data.get("title") or "").strip()
    pay         = (data.get("pay") or "").strip()
    hours       = (data.get("hours") or "").strip()
    exp         = int(data.get("experience_required") or 0)
    lang_pref   = (data.get("language_preference") or "").strip()
    location    = (data.get("location") or "").strip()
    description = (data.get("description") or "").strip()

    if not all([title, pay, hours]):
        return jsonify({'error': 'title, pay, and hours are required'}), 400

    import datetime as _datetime
    expires_at = _datetime.datetime.utcnow() + _datetime.timedelta(days=30)

    db = get_db()
    db.execute(
        """INSERT INTO jobs
           (employer_id, title, pay, hours, experience_required,
            language_preference, location, description, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user["id"], title, pay, hours, exp, lang_pref, location, description, expires_at),
    )
    db.commit()

    job = db.execute("SELECT * FROM jobs WHERE rowid = last_insert_rowid()").fetchone()
    return jsonify({'job': row_to_dict(job)}), 201


@app.route("/api/employer/jobs/<int:job_id>/toggle", methods=["POST"])
@api_login_required(role="employer")
def api_employer_toggle_job(job_id):
    user = get_current_user()
    db   = get_db()
    job  = db.execute(
        "SELECT * FROM jobs WHERE id = ? AND employer_id = ?", (job_id, user["id"])
    ).fetchone()
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    new_status = "closed" if job["status"] == "open" else "open"
    db.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, job_id))
    db.commit()
    return jsonify({'status': new_status})


@app.route("/api/employer/jobs/<int:job_id>/applications")
@api_login_required(role="employer")
def api_employer_job_applications(job_id):
    user = get_current_user()
    db   = get_db()
    job  = db.execute(
        "SELECT * FROM jobs WHERE id = ? AND employer_id = ?", (job_id, user["id"])
    ).fetchone()
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    applications = db.execute(
        """SELECT a.*,
                  u.name, u.email, u.phone, u.bio, u.experience_years, u.languages_spoken,
                  v.verification_status, v.age_verified,
                  v.face_match_score, v.extracted_name,
                  v.extracted_dob, v.id AS verification_id
           FROM applications a
           JOIN users u ON u.id = a.worker_id
           LEFT JOIN verifications v ON v.worker_id = a.worker_id
           WHERE a.job_id = ?
           ORDER BY a.ai_score DESC, a.created_at DESC""",
        (job_id,),
    ).fetchall()

    ev_row = db.execute(
        "SELECT business_verified FROM employer_verifications WHERE employer_id=?", (user["id"],)
    ).fetchone()
    employer_verified = bool(ev_row and ev_row["business_verified"])

    apps_out = []
    for a in applications:
        d = row_to_dict(a)
        refs = db.execute(
            """SELECT r.id, r.referring_employer_id, r.referral_note, r.created_at,
                      u.name AS employer_name, u.restaurant_name
               FROM referrals r
               JOIN users u ON u.id = r.referring_employer_id
               JOIN employer_verifications ev ON ev.employer_id = r.referring_employer_id
               WHERE r.worker_id = ? AND r.status = 'active' AND ev.business_verified = 1
               ORDER BY r.created_at DESC""",
            (a["worker_id"],),
        ).fetchall()
        d["referrals"]      = [row_to_dict(r) for r in refs]
        d["referral_count"] = len(d["referrals"])
        existing_ref = db.execute(
            "SELECT id FROM referrals WHERE referring_employer_id=? AND job_application_id=?",
            (user["id"], a["id"]),
        ).fetchone()
        d["already_referred"] = existing_ref is not None
        apps_out.append(d)

    return jsonify({
        "job": row_to_dict(job),
        "employer_verified": employer_verified,
        "applications": apps_out,
    })


@app.route("/api/employer/applications/<int:app_id>/status", methods=["POST"])
@api_login_required(role="employer")
def api_employer_update_application_status(app_id):
    user       = get_current_user()
    data       = request.get_json(force=True)
    new_status = data.get("status")

    if new_status not in ("pending", "reviewed", "accepted", "rejected", "hired"):
        return jsonify({'error': 'Invalid status'}), 400

    db      = get_db()
    app_row = db.execute(
        """SELECT a.*, j.employer_id FROM applications a
           JOIN jobs j ON j.id = a.job_id WHERE a.id = ?""",
        (app_id,),
    ).fetchone()

    if not app_row or app_row["employer_id"] != user["id"]:
        return jsonify({'error': 'Application not found'}), 404

    db.execute("UPDATE applications SET status = ? WHERE id = ?", (new_status, app_id))
    db.commit()
    return jsonify({'ok': True})


# Worker API

@app.route("/api/worker/jobs")
@api_login_required(role="worker")
def api_worker_jobs():
    db   = get_db()
    jobs = db.execute(
        """SELECT j.*, u.name AS employer_name, u.restaurant_name
           FROM jobs j JOIN users u ON u.id = j.employer_id
           WHERE j.status = 'open'
           ORDER BY j.created_at DESC""",
    ).fetchall()
    return jsonify({'jobs': [row_to_dict(j) for j in jobs]})


@app.route("/api/worker/jobs/<int:job_id>/apply", methods=["POST"])
@api_login_required(role="worker")
def api_worker_apply(job_id):
    user = get_current_user()
    db   = get_db()

    job = db.execute(
        """SELECT j.*, u.name AS employer_name, u.restaurant_name
           FROM jobs j JOIN users u ON u.id = j.employer_id
           WHERE j.id = ? AND j.status = 'open'""",
        (job_id,),
    ).fetchone()
    if not job:
        return jsonify({'error': 'Job not found or no longer available'}), 404

    if db.execute(
        "SELECT id FROM applications WHERE job_id=? AND worker_id=?", (job_id, user["id"])
    ).fetchone():
        return jsonify({'error': 'You have already applied to this job'}), 409

    data         = request.get_json(force=True)
    cover_letter = (data.get("cover_letter") or "").strip()

    verification = get_verification(user["id"])
    vstatus      = verification["verification_status"] if verification else None

    score, summary = screen_application(dict(job), dict(user), cover_letter, vstatus)

    db.execute(
        """INSERT INTO applications (job_id, worker_id, cover_letter, ai_score, ai_summary)
           VALUES (?, ?, ?, ?, ?)""",
        (job_id, user["id"], cover_letter, score, summary),
    )
    db.commit()

    application = db.execute(
        "SELECT * FROM applications WHERE rowid = last_insert_rowid()"
    ).fetchone()
    return jsonify({'application': row_to_dict(application)}), 201


@app.route("/api/worker/applications")
@api_login_required(role="worker")
def api_worker_applications():
    user = get_current_user()
    db   = get_db()
    apps = db.execute(
        """SELECT a.*, j.title, j.pay, j.hours, j.location,
                  u.name AS employer_name, u.restaurant_name
           FROM applications a
           JOIN jobs j ON j.id = a.job_id
           JOIN users u ON u.id = j.employer_id
           WHERE a.worker_id = ?
           ORDER BY a.created_at DESC""",
        (user["id"],),
    ).fetchall()
    return jsonify({'applications': [row_to_dict(a) for a in apps]})


@app.route("/api/worker/verify")
@api_login_required(role="worker")
def api_worker_verify_status():
    user         = get_current_user()
    verification = get_verification(user["id"])
    return jsonify({'verification': row_to_dict(verification)})


@app.route("/api/worker/verify/upload-id", methods=["POST"])
@api_login_required(role="worker")
def api_worker_upload_id():
    user = get_current_user()
    db   = get_db()

    f = request.files.get("id_document")
    if not f or not f.filename or not allowed_file(f.filename):
        return jsonify({'error': 'Please upload a JPG or PNG image of your ID'}), 400

    filepath = save_upload(f, "id", user["id"])

    existing = db.execute(
        "SELECT id FROM verifications WHERE worker_id=?", (user["id"],)
    ).fetchone()
    if existing:
        db.execute(
            """UPDATE verifications
               SET id_document_path=?, selfie_path=NULL,
                   verification_status='pending', failure_reason=NULL,
                   face_match_score=NULL, identity_verified=0,
                   extracted_name=NULL, extracted_dob=NULL, verified_at=NULL
               WHERE worker_id=?""",
            (filepath, user["id"]),
        )
    else:
        db.execute(
            "INSERT INTO verifications (worker_id, id_document_path) VALUES (?,?)",
            (user["id"], filepath),
        )
    db.commit()

    return jsonify({'step': 2, 'message': 'ID uploaded. Now upload a selfie to complete verification.'})


@app.route("/api/worker/verify/upload-selfie", methods=["POST"])
@api_login_required(role="worker")
def api_worker_upload_selfie():
    user         = get_current_user()
    db           = get_db()
    verification = get_verification(user["id"])

    if not verification or not verification["id_document_path"]:
        return jsonify({'error': 'Please upload your ID document first'}), 400

    f = request.files.get("selfie")
    if not f or not f.filename or not allowed_file(f.filename):
        return jsonify({'error': 'Please upload a JPG or PNG selfie'}), 400

    filepath = save_upload(f, "selfie", user["id"])
    db.execute("UPDATE verifications SET selfie_path=? WHERE worker_id=?", (filepath, user["id"]))
    db.commit()

    from ai_verification import run_verification
    import logging as _logging
    _log = _logging.getLogger(__name__)
    try:
        result = run_verification(
            user["id"],
            verification["id_document_path"],
            filepath,
            db,
        )
        updated = get_verification(user["id"])
        return jsonify({'verification': row_to_dict(updated)})
    except Exception as e:
        _log.error("upload_selfie: verification pipeline error for user %s: %s: %s",
                   user["id"], type(e).__name__, e)
        reason = str(e)
        db.execute(
            "UPDATE verifications SET failure_reason=? WHERE worker_id=?",
            (reason, user["id"]),
        )
        db.commit()
        updated = get_verification(user["id"])
        return jsonify({'verification': row_to_dict(updated), 'pipeline_error': reason})


@app.route("/api/worker/verify/resubmit", methods=["POST"])
@api_login_required(role="worker")
def api_worker_verify_resubmit():
    user = get_current_user()
    db   = get_db()
    db.execute(
        """UPDATE verifications
           SET id_document_path=NULL, selfie_path=NULL,
               verification_status='pending', failure_reason=NULL,
               face_match_score=NULL, identity_verified=0, age_verified=0,
               extracted_name=NULL, extracted_dob=NULL, verified_at=NULL
           WHERE worker_id=?""",
        (user["id"],),
    )
    db.commit()
    return jsonify({'ok': True})


@app.route("/api/worker/profile", methods=["PUT", "GET"])
@api_login_required(role="worker")
def api_worker_update_profile():
    user = get_current_user()
    db = get_db()

    if request.method == "GET":
        u = row_to_dict(user)
        u.pop('password_hash', None)
        u.pop('email_verification_token', None)
        return jsonify({'user': u})

    data = request.get_json(force=True)

    bio                = (data.get("bio") or "").strip()
    experience_years   = int(data.get("experience_years") or 0)
    languages_spoken   = (data.get("languages_spoken") or "").strip()
    phone              = (data.get("phone") or "").strip()
    skills             = (data.get("skills") or "").strip()
    availability       = (data.get("availability") or "").strip()
    dialect_preference = (data.get("dialect_preference") or "").strip()

    db.execute(
        """UPDATE users
           SET bio=?, experience_years=?, languages_spoken=?, phone=?,
               skills=?, availability=?, dialect_preference=?
           WHERE id=?""",
        (bio, experience_years, languages_spoken, phone, skills, availability, dialect_preference, user["id"]),
    )
    db.commit()

    updated = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    u = row_to_dict(updated)
    u.pop('password_hash', None)
    u.pop('email_verification_token', None)
    return jsonify({'user': u})


@app.route("/api/worker/jobs/<int:job_id>/translate", methods=["POST"])
@api_login_required(role="worker")
def api_worker_translate_job(job_id):
    """On-demand translation or plain-language simplification of a job description."""
    import anthropic as _anthropic
    import logging as _log

    data   = request.get_json(force=True)
    action = data.get("action", "simplify")   # "translate" | "simplify"
    lang   = data.get("lang", "en")

    job = get_db().execute(
        "SELECT * FROM jobs WHERE id = ? AND status = 'open'", (job_id,)
    ).fetchone()
    if not job:
        return jsonify({"error": "Job not found"}), 404

    description = (job["description"] or "").strip()
    if not description:
        return jsonify({"error": "This job has no description to process"}), 400

    lang_names = {
        "zh": "Simplified Chinese", "es": "Spanish",
        "fr": "French", "pt": "Portuguese", "vi": "Vietnamese", "en": "English",
    }

    if action == "translate":
        target = lang_names.get(lang, lang)
        prompt = (
            f"Translate the following job description into {target}. "
            "Return only the translated text, no preamble or explanation:\n\n"
            f"{description}"
        )
    else:
        prompt = (
            "Rewrite the following job description in simple, plain language. "
            "Use short sentences and common everyday words so someone who is not a "
            "native English speaker can understand it easily. "
            "Return only the rewritten text, no preamble:\n\n"
            f"{description}"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        return jsonify({"error": "ANTHROPIC_API_KEY is not configured on the server."}), 503

    try:
        client = _anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        result = message.content[0].text.strip()
        return jsonify({"result": result})
    except Exception as e:
        _log.getLogger(__name__).error("translate_job %s: %s: %s", job_id, type(e).__name__, e)
        return jsonify({"error": str(e)}), 500


# ── Employer verification API ─────────────────────────────────────────────────

def _get_employer_verification(employer_id: int):
    return get_db().execute(
        "SELECT * FROM employer_verifications WHERE employer_id = ?", (employer_id,)
    ).fetchone()


@app.route("/api/employer/verify")
@api_login_required(role="employer")
def api_employer_verify_status():
    user = get_current_user()
    ev   = _get_employer_verification(user["id"])
    return jsonify({"verification": row_to_dict(ev)})


@app.route("/api/employer/verify/submit", methods=["POST"])
@api_login_required(role="employer")
def api_employer_verify_submit():
    user = get_current_user()
    db   = get_db()

    business_name    = (request.form.get("business_name") or "").strip()
    business_address = (request.form.get("business_address") or "").strip()

    if not business_name or not business_address:
        return jsonify({"error": "Business name and address are required."}), 400

    f = request.files.get("business_document")
    if not f or not f.filename or not allowed_file(f.filename):
        return jsonify({"error": "Please upload a JPG or PNG photo of your business document."}), 400

    filepath = save_upload(f, "biz", user["id"])

    # Upsert employer_verifications row
    existing = _get_employer_verification(user["id"])
    if existing:
        db.execute(
            """UPDATE employer_verifications
               SET business_license_path=?, business_name_entered=?, address_entered=?,
                   extracted_business_name=NULL, extracted_address=NULL, document_type=NULL,
                   match_confidence=NULL, business_verified=0,
                   business_verification_status='pending', failure_reason=NULL, verified_at=NULL
               WHERE employer_id=?""",
            (filepath, business_name, business_address, user["id"]),
        )
    else:
        db.execute(
            """INSERT INTO employer_verifications
               (employer_id, business_license_path, business_name_entered, address_entered)
               VALUES (?, ?, ?, ?)""",
            (user["id"], filepath, business_name, business_address),
        )
    db.commit()

    from ai_employer_verification import run_employer_verification
    import logging as _logging
    _log = _logging.getLogger(__name__)
    try:
        run_employer_verification(user["id"], filepath, business_name, business_address, db)
    except Exception as e:
        _log.error("employer verify pipeline error for user %s: %s", user["id"], e)
        db.execute(
            "UPDATE employer_verifications SET failure_reason=? WHERE employer_id=?",
            (str(e), user["id"]),
        )
        db.commit()

    ev = _get_employer_verification(user["id"])
    return jsonify({"verification": row_to_dict(ev)})


# ── Referrals API ─────────────────────────────────────────────────────────────

def _worker_referrals(worker_id: int):
    """Return active referrals for a worker, only from currently verified businesses."""
    return get_db().execute(
        """SELECT r.id, r.referring_employer_id, r.referral_note, r.created_at,
                  u.name AS employer_name, u.restaurant_name,
                  ev.business_verified
           FROM referrals r
           JOIN users u ON u.id = r.referring_employer_id
           LEFT JOIN employer_verifications ev ON ev.employer_id = r.referring_employer_id
           WHERE r.worker_id = ? AND r.status = 'active' AND ev.business_verified = 1
           ORDER BY r.created_at DESC""",
        (worker_id,),
    ).fetchall()


@app.route("/api/employer/applications/<int:app_id>/refer", methods=["POST"])
@api_login_required(role="employer")
def api_employer_refer_worker(app_id):
    user = get_current_user()
    db   = get_db()

    # Employer must be business-verified to issue referrals
    ev = _get_employer_verification(user["id"])
    if not ev or not ev["business_verified"]:
        return jsonify({"error": "Verify your business to refer workers."}), 403

    app_row = db.execute(
        """SELECT a.*, j.employer_id FROM applications a
           JOIN jobs j ON j.id = a.job_id WHERE a.id = ?""",
        (app_id,),
    ).fetchone()
    if not app_row or app_row["employer_id"] != user["id"]:
        return jsonify({"error": "Application not found."}), 404
    if app_row["status"] != "hired":
        return jsonify({"error": "Referrals can only be created for hired workers."}), 400

    data          = request.get_json(force=True)
    referral_note = (data.get("note") or "").strip()[:200]

    try:
        db.execute(
            """INSERT INTO referrals
               (referring_employer_id, worker_id, job_application_id, referral_note)
               VALUES (?, ?, ?, ?)""",
            (user["id"], app_row["worker_id"], app_id, referral_note or None),
        )
        db.commit()
    except Exception:
        return jsonify({"error": "You have already referred this worker for this application."}), 409

    return jsonify({"ok": True}), 201


@app.route("/api/employer/referrals/<int:referral_id>/revoke", methods=["POST"])
@api_login_required(role="employer")
def api_employer_revoke_referral(referral_id):
    user = get_current_user()
    db   = get_db()
    ref  = db.execute(
        "SELECT * FROM referrals WHERE id = ? AND referring_employer_id = ?",
        (referral_id, user["id"]),
    ).fetchone()
    if not ref:
        return jsonify({"error": "Referral not found."}), 404
    db.execute("UPDATE referrals SET status = 'revoked' WHERE id = ?", (referral_id,))
    db.commit()
    return jsonify({"ok": True})


# Also expose applications endpoint with referral + employer_verified data
# (overrides the earlier definition by re-declaring it)

@app.route("/api/employer/jobs/<int:job_id>/applications/v2")
@api_login_required(role="employer")
def api_employer_job_applications_v2(job_id):
    """Extended version including referrals per worker and employer verified status."""
    user = get_current_user()
    db   = get_db()

    job = db.execute(
        "SELECT * FROM jobs WHERE id = ? AND employer_id = ?", (job_id, user["id"])
    ).fetchone()
    if not job:
        return jsonify({"error": "Job not found"}), 404

    applications = db.execute(
        """SELECT a.*,
                  u.name, u.email, u.phone, u.bio, u.experience_years, u.languages_spoken,
                  v.verification_status, v.age_verified,
                  v.face_match_score, v.extracted_name,
                  v.extracted_dob, v.id AS verification_id
           FROM applications a
           JOIN users u ON u.id = a.worker_id
           LEFT JOIN verifications v ON v.worker_id = a.worker_id
           WHERE a.job_id = ?
           ORDER BY a.ai_score DESC, a.created_at DESC""",
        (job_id,),
    ).fetchall()

    ev             = _get_employer_verification(user["id"])
    employer_verified = bool(ev and ev["business_verified"])

    apps_out = []
    for a in applications:
        d = row_to_dict(a)
        refs = _worker_referrals(a["worker_id"])
        d["referrals"]      = [row_to_dict(r) for r in refs]
        d["referral_count"] = len(d["referrals"])
        # Has this employer already referred this worker for this app?
        existing_ref = db.execute(
            "SELECT id FROM referrals WHERE referring_employer_id=? AND job_application_id=?",
            (user["id"], a["id"]),
        ).fetchone()
        d["already_referred"] = existing_ref is not None
        apps_out.append(d)

    return jsonify({
        "job": row_to_dict(job),
        "employer_verified": employer_verified,
        "applications": apps_out,
    })


# ── Interview Scheduling API ──────────────────────────────────────────────────

@app.route("/api/worker/applications/<int:app_id>/availability", methods=["PUT"])
@api_login_required(role="worker")
def api_worker_set_availability(app_id):
    """Save worker's availability for interviews on a specific application."""
    user = get_current_user()
    db = get_db()

    app_row = db.execute(
        "SELECT * FROM applications WHERE id = ? AND worker_id = ?", (app_id, user["id"])
    ).fetchone()
    if not app_row:
        return jsonify({"error": "Application not found"}), 404

    data = request.get_json(force=True)
    days = data.get("days", [])
    times = data.get("times", [])

    if not days or not times:
        return jsonify({"error": "Days and times are required"}), 400

    availability_data = {"days": days, "times": times}
    db.execute(
        "UPDATE applications SET worker_availability = ? WHERE id = ?",
        (json.dumps(availability_data), app_id),
    )
    db.commit()

    updated = db.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    return jsonify({"application": row_to_dict(updated)}), 200


@app.route("/api/worker/applications/<int:app_id>/availability", methods=["GET"])
@api_login_required(role="worker")
def api_worker_get_availability(app_id):
    """Get saved availability for an application."""
    user = get_current_user()
    db = get_db()

    app_row = db.execute(
        "SELECT * FROM applications WHERE id = ? AND worker_id = ?", (app_id, user["id"])
    ).fetchone()
    if not app_row:
        return jsonify({"error": "Application not found"}), 404

    availability = None
    if app_row["worker_availability"]:
        try:
            availability = json.loads(app_row["worker_availability"])
        except json.JSONDecodeError:
            availability = None

    return jsonify({"availability": availability}), 200


@app.route("/api/employer/applications/<int:app_id>/schedule-interview", methods=["POST"])
@api_login_required(role="employer")
def api_employer_schedule_interview(app_id):
    """Schedule an interview for a specific application."""
    user = get_current_user()
    db = get_db()

    app_row = db.execute(
        """SELECT a.*, j.employer_id, j.title, u.name AS worker_name, u.email AS worker_email
           FROM applications a
           JOIN jobs j ON j.id = a.job_id
           JOIN users u ON u.id = a.worker_id
           WHERE a.id = ?""",
        (app_id,),
    ).fetchone()

    if not app_row or app_row["employer_id"] != user["id"]:
        return jsonify({"error": "Application not found"}), 404

    if app_row["status"] == "interview_scheduled":
        return jsonify({"error": "Interview already scheduled for this application"}), 409

    data = request.get_json(force=True)
    scheduled_at_str = data.get("scheduled_at")

    if not scheduled_at_str:
        return jsonify({"error": "scheduled_at is required"}), 400

    try:
        scheduled_at = datetime.fromisoformat(scheduled_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return jsonify({"error": "Invalid date format"}), 400

    from google_calendar import create_interview_event

    google_event_id = create_interview_event(
        employer_email=user["email"],
        worker_email=app_row["worker_email"],
        scheduled_at=scheduled_at,
        job_title=app_row["title"],
        restaurant_name=user["restaurant_name"] or user["name"],
        worker_name=app_row["worker_name"],
        worker_language=app_row.get("language_pref", "en"),
    )

    db.execute(
        """INSERT INTO interviews (application_id, employer_id, worker_id, scheduled_at, google_event_id, calendar_invite_sent)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (app_id, user["id"], app_row["worker_id"], scheduled_at, google_event_id or None, 1 if google_event_id else 0),
    )
    db.execute(
        "UPDATE applications SET status = 'interview_scheduled' WHERE id = ?", (app_id,)
    )
    db.commit()

    interview = db.execute(
        "SELECT * FROM interviews WHERE application_id = ?", (app_id,)
    ).fetchone()

    return jsonify({"interview": row_to_dict(interview)}), 201


@app.route("/api/worker/interviews", methods=["GET"])
@api_login_required(role="worker")
def api_worker_list_interviews():
    """List all scheduled interviews for a worker."""
    user = get_current_user()
    db = get_db()

    interviews = db.execute(
        """SELECT i.*, a.job_id, j.title, j.location, u.name AS employer_name, u.restaurant_name
           FROM interviews i
           JOIN applications a ON a.id = i.application_id
           JOIN jobs j ON j.id = a.job_id
           JOIN users u ON u.id = i.employer_id
           WHERE i.worker_id = ? AND i.status = 'scheduled'
           ORDER BY i.scheduled_at ASC""",
        (user["id"],),
    ).fetchall()

    return jsonify({"interviews": [row_to_dict(i) for i in interviews]}), 200


@app.route("/api/employer/interviews", methods=["GET"])
@api_login_required(role="employer")
def api_employer_list_interviews():
    """List all scheduled interviews for an employer."""
    user = get_current_user()
    db = get_db()

    interviews = db.execute(
        """SELECT i.*, a.job_id, j.title, u.name AS worker_name, u.email AS worker_email
           FROM interviews i
           JOIN applications a ON a.id = i.application_id
           JOIN jobs j ON j.id = a.job_id
           JOIN users u ON u.id = i.worker_id
           WHERE i.employer_id = ? AND i.status = 'scheduled'
           ORDER BY i.scheduled_at ASC""",
        (user["id"],),
    ).fetchall()

    return jsonify({"interviews": [row_to_dict(i) for i in interviews]}), 200


@app.route("/api/interviews/<int:interview_id>", methods=["GET"])
@api_login_required()
def api_get_interview_detail(interview_id):
    """Get details of a specific interview."""
    user = get_current_user()
    db = get_db()

    interview = db.execute(
        "SELECT * FROM interviews WHERE id = ?", (interview_id,)
    ).fetchone()

    if not interview:
        return jsonify({"error": "Interview not found"}), 404

    if interview["employer_id"] != user["id"] and interview["worker_id"] != user["id"]:
        return jsonify({"error": "Access denied"}), 403

    return jsonify({"interview": row_to_dict(interview)}), 200


# ── Password Reset API ────────────────────────────────────────────────────────

@app.route("/api/auth/forgot-password", methods=["POST"])
def api_forgot_password():
    """Request password reset link."""
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if not user:
        return jsonify({"ok": True})

    import secrets as _secrets
    import datetime as _datetime

    token = _secrets.token_urlsafe(32)
    expiry = _datetime.datetime.utcnow() + _datetime.timedelta(hours=1)

    db.execute(
        "UPDATE users SET password_reset_token = ?, password_reset_expiry = ? WHERE id = ?",
        (token, expiry, user["id"]),
    )
    db.commit()

    from email_service import send_password_reset_email
    send_password_reset_email(email, user["name"], token, user["language_pref"])

    return jsonify({"ok": True})


@app.route("/api/auth/reset-password", methods=["POST"])
def api_reset_password():
    """Reset password with token."""
    data = request.get_json(force=True)
    token = (data.get("token") or "").strip()
    new_password = data.get("new_password") or ""

    if not token or not new_password:
        return jsonify({"error": "Token and password required"}), 400

    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE password_reset_token = ? AND password_reset_expiry > datetime('now')",
        (token,),
    ).fetchone()

    if not user:
        return jsonify({"error": "Invalid or expired token"}), 400

    pw_hash = generate_password_hash(new_password)
    db.execute(
        "UPDATE users SET password_hash = ?, password_reset_token = NULL, password_reset_expiry = NULL WHERE id = ?",
        (pw_hash, user["id"]),
    )
    db.commit()

    return jsonify({"ok": True})


# ── Account Deletion ──────────────────────────────────────────────────────────

@app.route("/api/user/delete-account", methods=["POST"])
@api_login_required()
def api_delete_account():
    """Delete user account and all associated data."""
    from datetime import datetime as _dt
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    db = get_db()
    deletion_time = _dt.utcnow()

    # Capture PII before any mutations so the confirmation email can still be sent.
    user_id    = user["id"]
    user_email = user["email"]
    user_name  = user["name"]
    user_lang  = user["language_pref"] or "en"

    try:
        if user["role"] == "employer":
            # FK-safe deletion order:
            # referrals → interviews → applications → employer_verifications → jobs
            # (referrals and interviews both reference applications; applications reference jobs)
            db.execute("DELETE FROM referrals WHERE referring_employer_id = ?", (user_id,))
            db.execute("DELETE FROM interviews WHERE employer_id = ?",          (user_id,))
            db.execute(
                "DELETE FROM applications WHERE job_id IN (SELECT id FROM jobs WHERE employer_id = ?)",
                (user_id,),
            )
            db.execute("DELETE FROM employer_verifications WHERE employer_id = ?", (user_id,))
            db.execute("DELETE FROM jobs WHERE employer_id = ?",                   (user_id,))

        elif user["role"] == "worker":
            # FK-safe deletion order:
            # referrals → interviews → applications → verifications
            db.execute("DELETE FROM referrals    WHERE worker_id = ?", (user_id,))
            db.execute("DELETE FROM interviews   WHERE worker_id = ?", (user_id,))
            db.execute("DELETE FROM applications WHERE worker_id = ?", (user_id,))
            db.execute("DELETE FROM verifications WHERE worker_id = ?", (user_id,))

        # Replace email with an untraceable placeholder — cannot set NULL because the
        # column has NOT NULL constraint, and UNIQUE means we need a distinct value per row.
        placeholder = f"deleted_{user_id}_{int(deletion_time.timestamp())}@deleted.invalid"
        db.execute(
            "UPDATE users SET deleted_at = ?, email = ? WHERE id = ?",
            (deletion_time, placeholder, user_id),
        )
        db.commit()

    except Exception as e:
        db.rollback()
        app.logger.error("Account deletion failed for user %s: %s", user_id, e, exc_info=True)
        return jsonify({"error": f"Deletion failed: {str(e)}"}), 500

    # Best-effort confirmation email — never block the response on this.
    try:
        from email_service import send_account_deleted_email
        send_account_deleted_email(user_email, user_name, user_lang)
    except Exception as e:
        app.logger.warning("Could not send account-deleted email to %s: %s", user_email, e)

    session.clear()
    return jsonify({"ok": True})


# ── Job Sharing & QR Code ─────────────────────────────────────────────────────

@app.route("/api/jobs/<int:job_id>/qrcode")
def api_generate_qrcode(job_id):
    """Generate QR code for job listing."""
    db = get_db()
    job = db.execute("SELECT * FROM jobs WHERE id = ? AND status = 'open'", (job_id,)).fetchone()

    if not job:
        abort(404)

    try:
        import qrcode
        import io
        from PIL import Image

        frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
        job_url = f"{frontend_url}/jobs/{job_id}"

        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(job_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        img_io = io.BytesIO()
        img.save(img_io, "PNG")
        img_io.seek(0)

        return send_file(img_io, mimetype="image/png", as_attachment=True, download_name=f"job_{job_id}.png")
    except Exception as e:
        log.error(f"QR code generation error: {e}")
        return jsonify({"error": "Could not generate QR code"}), 500


# ── Public Job Listings ───────────────────────────────────────────────────────

@app.route("/jobs/<int:job_id>")
def public_job_detail(job_id):
    """Public job listing page (no login required)."""
    db = get_db()
    job = db.execute(
        """SELECT j.*, u.name AS employer_name, u.restaurant_name
           FROM jobs j JOIN users u ON u.id = j.employer_id
           WHERE j.id = ? AND j.status = 'open'""",
        (job_id,),
    ).fetchone()

    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("index"))

    user = get_current_user()
    applied = False
    if user and user["role"] == "worker":
        applied = bool(
            db.execute(
                "SELECT id FROM applications WHERE job_id = ? AND worker_id = ?",
                (job_id, user["id"]),
            ).fetchone()
        )

    return render_template("public_job_detail.html", user=user, job=job, applied=applied)


@app.route("/api/jobs/<int:job_id>/public")
def api_public_job_detail(job_id):
    """Get public job details (no authentication required)."""
    db = get_db()
    job = db.execute(
        """SELECT j.*, u.name AS employer_name, u.restaurant_name
           FROM jobs j JOIN users u ON u.id = j.employer_id
           WHERE j.id = ? AND j.status = 'open'""",
        (job_id,),
    ).fetchone()

    if not job:
        return jsonify({"error": "Job not found"}), 404

    job_dict = row_to_dict(job)
    job_dict.pop("employer_id", None)
    return jsonify({"job": job_dict})


# ── Job Expiry Management ─────────────────────────────────────────────────────

@app.route("/api/employer/jobs/<int:job_id>/renew", methods=["POST"])
@api_login_required(role="employer")
def api_renew_job(job_id):
    """Renew a job listing for another 30 days."""
    user = get_current_user()
    db = get_db()

    job = db.execute(
        "SELECT * FROM jobs WHERE id = ? AND employer_id = ?", (job_id, user["id"])
    ).fetchone()

    if not job:
        return jsonify({"error": "Job not found"}), 404

    import datetime as _datetime

    new_expiry = _datetime.datetime.utcnow() + _datetime.timedelta(days=30)

    db.execute(
        "UPDATE jobs SET expires_at = ? WHERE id = ?",
        (new_expiry, job_id),
    )
    db.commit()

    return jsonify({"ok": True, "expires_at": new_expiry.isoformat()})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
