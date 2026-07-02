import os
import re
import time
import uuid
import json
import logging
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone as _tz


def _to_naive_utc(dt: datetime) -> datetime:
    """Normalize to timezone-naive UTC so sqlite's TIMESTAMP converter can read it back."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(_tz.utc).replace(tzinfo=None)
    return dt
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


def send_verification_email_async(email: str, name: str, token: str, lang: str = "en") -> None:
    """
    Fire the verification email from a background thread so signup responds
    immediately. flask-mailman needs an app context inside the thread.
    """
    def _task():
        with app.app_context():
            try:
                send_verification_email(email, name, token, lang)
            except Exception:
                log.exception("async verification email failed for %s", email)

    threading.Thread(target=_task, daemon=True).start()

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

def _load_secret_key() -> str:
    """
    SECRET_KEY from env, or a generated key persisted to a file so all
    gunicorn workers share it. Never fall back to a guessable constant —
    that would make session cookies forgeable.
    """
    key = os.environ.get("SECRET_KEY")
    if key and key != "change_this_to_a_random_secret_key":
        return key
    import secrets as _secrets
    import tempfile
    key_path = os.path.join(tempfile.gettempdir(), "entr_secret.key")
    try:
        with open(key_path, "r") as f:
            stored = f.read().strip()
        if len(stored) >= 32:
            return stored
    except OSError:
        pass
    generated = _secrets.token_hex(32)
    try:
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(generated)
    except FileExistsError:
        with open(key_path, "r") as f:
            return f.read().strip() or generated
    except OSError:
        pass
    logging.getLogger(__name__).warning(
        "SECRET_KEY env var not set — using a generated key. Set SECRET_KEY in "
        "Railway so sessions survive restarts and redeploys."
    )
    return generated


app = Flask(__name__)
app.secret_key = _load_secret_key()
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
# Sessions expire after 7 days; logout clears them immediately.
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

CORS(
    app,
    origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
        "https://entr.up.railway.app",
    ],
    supports_credentials=True,
)
init_mail(app)


@app.before_request
def _make_session_permanent():
    session.permanent = True
    g._request_start = time.monotonic()


# ── Security headers ──────────────────────────────────────────────────────────

@app.after_request
def _security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "frame-ancestors 'none'",
    )
    return resp


# ── Request logging ───────────────────────────────────────────────────────────

@app.after_request
def _request_log(resp):
    try:
        duration_ms = (time.monotonic() - getattr(g, "_request_start", time.monotonic())) * 1000
        log.info("%s %s -> %s (%.0fms)", request.method, request.path, resp.status_code, duration_ms)
    except Exception:
        pass
    return resp


# ── Global error handler ──────────────────────────────────────────────────────

@app.errorhandler(Exception)
def _handle_unexpected_error(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        # Preserve intentional aborts (404/403/etc.) with a JSON body for API paths
        if request.path.startswith("/api/"):
            return jsonify({"error": e.description or e.name}), e.code
        return e
    log.exception("Unhandled exception on %s %s", request.method, request.path)
    return jsonify({"error": "Something went wrong on our side. Please try again."}), 500


# ── Rate limiting (in-memory sliding window) ──────────────────────────────────

_rate_lock = threading.Lock()
_ip_hits: dict = defaultdict(deque)       # ip -> deque of timestamps
_ai_hits: dict = defaultdict(deque)       # user/ip key -> deque of timestamps

# Counters live in each gunicorn worker's memory, so divide the global budget
# by worker count to keep effective limits at ~100 req/IP/min and ~10 AI
# calls/user/min across the whole service.
_WORKERS = max(1, int(os.environ.get("GUNICORN_WORKERS", "2")))
RATE_LIMIT_PER_MIN = max(1, 100 // _WORKERS)      # all endpoints, per IP
AI_RATE_LIMIT_PER_MIN = max(1, 10 // _WORKERS)    # AI-powered endpoints, per user


def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else (request.remote_addr or "unknown")


def _hit(bucket: dict, key: str, limit: int, window: float = 60.0) -> bool:
    """Record a hit; return True if within limit."""
    now = time.monotonic()
    with _rate_lock:
        q = bucket[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


@app.before_request
def _global_rate_limit():
    if request.method == "OPTIONS":
        return None
    if not _hit(_ip_hits, _client_ip(), RATE_LIMIT_PER_MIN):
        return jsonify({"error": "Too many requests. Please slow down and try again."}), 429
    return None


def ai_rate_limited() -> bool:
    """Per-user limiter for endpoints that call Claude. True = over the limit."""
    key = f"user:{session.get('user_id')}" if session.get("user_id") else f"ip:{_client_ip()}"
    return not _hit(_ai_hits, key, AI_RATE_LIMIT_PER_MIN)


# ── Input sanitization ────────────────────────────────────────────────────────

_TAG_RE = re.compile(r"<[^>]*>")

def clean_text(value, max_len: int = 2000) -> str:
    """Strip HTML tags, control chars, and cap length. Safe for any text input."""
    if value is None:
        return ""
    text = str(value)
    text = _TAG_RE.sub("", text)
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return text.strip()[:max_len]

try:
    init_db()
    log.info("Database initialized successfully")
except Exception:
    log.exception("STARTUP ERROR: failed to initialize database")

# Verification uploads stored OUTSIDE static/ so they are never web-accessible
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "verification")
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except OSError:
    log.exception("STARTUP ERROR: failed to create upload folder %s", UPLOAD_FOLDER)
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
    user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        return None
    # Server-side invalidation: cookies from before the last logout carry a
    # stale epoch and are rejected even though their signature is valid.
    try:
        current_epoch = user["session_epoch"] or 0
    except (IndexError, KeyError):
        current_epoch = 0
    if session.get("epoch", 0) != current_epoch:
        return None
    return user


def _establish_session(user_row):
    """Create a session for a user, pinned to their current session epoch."""
    try:
        epoch = user_row["session_epoch"] or 0
    except (IndexError, KeyError):
        epoch = 0
    session["user_id"] = user_row["id"]
    session["epoch"]   = epoch


def _invalidate_all_sessions(user_id: int):
    """Bump the user's epoch so every outstanding session cookie is rejected."""
    db = get_db()
    db.execute(
        "UPDATE users SET session_epoch = COALESCE(session_epoch, 0) + 1 WHERE id = ?",
        (user_id,),
    )
    db.commit()


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


# ── Health check ──────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }), 200


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

        send_verification_email_async(email, name, token, language_pref)
        flash("Check your email. We sent a verification link — click it to activate your account.", "info")
        return redirect(url_for("login"))

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

        if not user["email_verified"]:
            flash("Please verify your email before logging in. Check your inbox.", "error")
            return render_template("login.html")

        _establish_session(user)
        session["lang"] = user["language_pref"]

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
    if session.get("user_id"):
        _invalidate_all_sessions(session["user_id"])
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
        title         = request.form.get("title", "").strip()
        pay_amount    = request.form.get("pay_amount", "").strip()
        pay_type      = request.form.get("pay_type", "per_hour").strip()
        tips_included = request.form.get("tips_included", "no").strip()
        hours         = request.form.get("hours", "").strip()
        exp           = int(request.form.get("experience_required", 0) or 0)
        location      = request.form.get("location", "").strip()
        skills_req    = request.form.get("skills_required", "").strip()
        add_info      = request.form.get("additional_info", "").strip()

        if not all([title, pay_amount, hours]):
            flash("Position, pay, and hours are required.", "error")
            return render_template("employer/post_job.html", user=user)

        pay_suffixes = {
            "per_hour": "/hr", "per_day": "/day", "per_week": "/week",
            "per_month": "/month", "salary_year": "/yr",
        }
        pay = f"${pay_amount}{pay_suffixes.get(pay_type, '/hr')}"
        if tips_included == "yes":
            pay += " + tips"

        parts = []
        if skills_req:
            parts.append(f"Skills required: {skills_req}")
        if add_info:
            parts.append(f"Additional info: {add_info}")
        description = "\n\n".join(parts)

        import datetime as _datetime
        expires_at = _datetime.datetime.utcnow() + _datetime.timedelta(days=30)

        db = get_db()
        db.execute(
            """INSERT INTO jobs
               (employer_id, title, pay, hours, experience_required,
                language_preference, location, description, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user["id"], title, pay, hours, exp, "", location, description, expires_at),
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
    email           = clean_text(data.get("email"), 254).lower()
    password        = data.get("password") or ""
    name            = clean_text(data.get("name"), 100)
    role            = data.get("role") or ""
    language_pref   = clean_text(data.get("language_pref"), 8) or "en"
    restaurant_name = clean_text(data.get("restaurant_name"), 120)
    phone           = clean_text(data.get("phone"), 30)
    date_of_birth   = clean_text(data.get("date_of_birth"), 10)   # YYYY-MM-DD
    us_state        = clean_text(data.get("us_state"), 2).upper()
    tos_accepted    = bool(data.get("tos_accepted"))

    if not all([email, password, name, role]):
        return jsonify({'error': 'Please fill in all required fields'}), 400

    if role not in ("employer", "worker"):
        return jsonify({'error': 'Invalid role'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    if not tos_accepted:
        return jsonify({'error': 'Please agree to the Privacy Policy and Terms of Service'}), 400

    under_18 = False
    if date_of_birth:
        try:
            from datetime import date as _date
            dob = _date.fromisoformat(date_of_birth)
            today = _date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            under_18 = age < 18
        except ValueError:
            return jsonify({'error': 'Invalid date of birth'}), 400

    db = get_db()
    if db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
        return jsonify({'error': 'An account with that email already exists'}), 409

    import secrets as _secrets
    token   = _secrets.token_urlsafe(32)
    pw_hash = generate_password_hash(password)
    db.execute(
        """INSERT INTO users
           (email, password_hash, role, name, phone, language_pref, restaurant_name,
            email_verified, email_verification_token, date_of_birth, us_state, tos_accepted_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, CURRENT_TIMESTAMP)""",
        (email, pw_hash, role, name, phone, language_pref, restaurant_name, token,
         date_of_birth or None, us_state or None),
    )
    db.commit()

    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    # No session here: the account activates only after the email link is clicked.

    # Queue the verification email in a background thread — signup returns immediately
    send_verification_email_async(email, name, token, language_pref)
    sent = True

    u = row_to_dict(user)
    u.pop('password_hash', None)
    u.pop('email_verification_token', None)
    return jsonify({'user': u, 'verification_email_sent': sent, 'under_18': under_18}), 201


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    data     = request.get_json(force=True)
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({'error': 'Invalid email or password'}), 401

    if not user["email_verified"]:
        return jsonify({
            'error': 'Please verify your email before logging in. Check your inbox.',
            'email_unverified': True,
        }), 403

    _establish_session(user)
    session["lang"] = user["language_pref"]

    u = row_to_dict(user)
    u.pop('password_hash', None)
    u.pop('email_verification_token', None)
    return jsonify({'user': u})


@app.route("/api/verify-email", methods=["GET"])
def api_verify_email_link():
    """
    Email-link verification target. Marks the account verified and bounces
    the user to the frontend login page with a status flag.
    """
    frontend = os.environ.get("FRONTEND_URL", "https://entr.up.railway.app").rstrip("/")
    token = (request.args.get("token") or "").strip()
    if not token:
        return redirect(f"{frontend}/login?verify_error=1")

    db   = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE email_verification_token = ?", (token,)
    ).fetchone()
    if not user:
        return redirect(f"{frontend}/login?verify_error=1")

    db.execute(
        "UPDATE users SET email_verified = 1, email_verification_token = NULL WHERE id = ?",
        (user["id"],),
    )
    db.commit()
    return redirect(f"{frontend}/login?verified=1")


_resend_hits: dict = defaultdict(deque)


@app.route("/api/resend-verification", methods=["POST"])
def api_resend_verification_public():
    """
    Unauthenticated resend (users can't log in before verifying).
    Always returns ok so account existence isn't leaked.
    """
    import secrets as _secrets

    data  = request.get_json(force=True)
    email = clean_text(data.get("email"), 254).lower()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Max 3 resends per email/IP per 5 minutes
    if not _hit(_resend_hits, f"{email}|{_client_ip()}", 3, window=300.0):
        return jsonify({"error": "Please wait a few minutes before requesting another email."}), 429

    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    sent = False
    if user and not user["email_verified"]:
        token = _secrets.token_urlsafe(32)
        db.execute(
            "UPDATE users SET email_verification_token = ? WHERE id = ?", (token, user["id"])
        )
        db.commit()
        sent = send_verification_email(email, user["name"], token, user["language_pref"] or "en")

    return jsonify({"ok": True, "sent": sent})


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
    if session.get("user_id"):
        _invalidate_all_sessions(session["user_id"])
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


PAY_TYPES = {
    "per_hour": "/hr", "per_day": "/day", "per_week": "/week",
    "biweekly": " biweekly", "per_month": "/month", "salary_year": "/yr",
}
HOURS_OPTIONS = {
    "full_time":     "Full-time (35–40 hrs/wk)",
    "part_time":     "Part-time (15–25 hrs/wk)",
    "weekends_only": "Weekends Only",
    "flexible":      "Flexible",
    "on_call":       "On-call",
}
CONTACT_FIELDS = ("contact_phone", "contact_whatsapp", "contact_wechat",
                  "contact_line", "contact_gchat")


@app.route("/api/employer/jobs", methods=["POST"])
@api_login_required(role="employer")
def api_employer_create_job():
    user = get_current_user()
    data = request.get_json(force=True)

    title      = clean_text(data.get("title"), 120)
    location   = clean_text(data.get("location"), 200)
    exp        = int(data.get("experience_required") or 0)

    # Structured pay (Step 2)
    pay_amount = clean_text(data.get("pay_amount"), 20)
    pay_type   = clean_text(data.get("pay_type"), 20) or "per_hour"
    tips       = 1 if data.get("tips_included") in (True, "yes", "true", 1) else 0

    # Hours dropdown (Step 2)
    hours_key  = clean_text(data.get("hours"), 40)

    # Free-text sections (Step 2)
    skills_text     = clean_text(data.get("skills_text"), 1000)
    additional_info = clean_text(data.get("additional_info"), 2000)

    # Contact methods (Step 3)
    contacts = {f: clean_text(data.get(f), 120) for f in CONTACT_FIELDS}

    # Legacy fallback: old clients send a raw `pay` string
    legacy_pay = clean_text(data.get("pay"), 60)

    if not title:
        return jsonify({'error': 'Job title is required'}), 400
    if not pay_amount and not legacy_pay:
        return jsonify({'error': 'Pay is required'}), 400
    if pay_amount:
        try:
            float(pay_amount.replace(",", ""))
        except ValueError:
            return jsonify({'error': 'Pay must be a number'}), 400
        if pay_type not in PAY_TYPES:
            return jsonify({'error': 'Invalid pay period'}), 400
    if not hours_key:
        return jsonify({'error': 'Hours are required'}), 400
    if not any(contacts.values()):
        return jsonify({'error': 'Please add at least one contact method so workers can reach you'}), 400

    # Display strings
    if pay_amount:
        pay = f"${pay_amount}{PAY_TYPES[pay_type]}"
        if tips:
            pay += " + tips"
    else:
        pay = legacy_pay
    hours = HOURS_OPTIONS.get(hours_key, clean_text(data.get("hours"), 80))

    parts = []
    if skills_text:
        parts.append(f"Skills needed: {skills_text}")
    if additional_info:
        parts.append(additional_info)
    legacy_desc = clean_text(data.get("description"), 2000)
    if legacy_desc and not parts:
        parts.append(legacy_desc)
    description = "\n\n".join(parts)

    import datetime as _datetime
    expires_at = _datetime.datetime.utcnow() + _datetime.timedelta(days=30)

    db = get_db()
    db.execute(
        """INSERT INTO jobs
           (employer_id, title, pay, hours, experience_required,
            language_preference, location, description, expires_at,
            pay_amount, pay_type, tips_included, skills_text, additional_info,
            contact_phone, contact_whatsapp, contact_wechat, contact_line, contact_gchat)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user["id"], title, pay, hours, exp, "", location, description, expires_at,
         pay_amount or None, pay_type if pay_amount else None, tips,
         skills_text or None, additional_info or None,
         contacts["contact_phone"] or None, contacts["contact_whatsapp"] or None,
         contacts["contact_wechat"] or None, contacts["contact_line"] or None,
         contacts["contact_gchat"] or None),
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
    cover_letter = clean_text(data.get("cover_letter"), 3000)

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

    bio                = clean_text(data.get("bio"), 2000)
    experience_years   = int(data.get("experience_years") or 0)
    languages_spoken   = clean_text(data.get("languages_spoken"), 200)
    phone              = clean_text(data.get("phone"), 30)
    skills             = clean_text(data.get("skills"), 1000)
    availability       = clean_text(data.get("availability"), 500)
    dialect_preference = clean_text(data.get("dialect_preference"), 100)

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

    if ai_rate_limited():
        return jsonify({"error": "Too many AI requests. Please wait a minute and try again."}), 429

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

    business_name    = clean_text(request.form.get("business_name"), 200)
    business_address = clean_text(request.form.get("business_address"), 300)

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
        scheduled_at = _to_naive_utc(datetime.fromisoformat(scheduled_at_str.replace("Z", "+00:00")))
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
        worker_language="en",
        employer_token_row=_get_oauth_token(user["id"]),
        worker_token_row=_get_oauth_token(app_row["worker_id"]),
    )

    # Manual fallback / belt-and-braces: always email both parties a confirmation.
    email_sent = 0
    try:
        from email_service import send_interview_scheduled_email
        when = scheduled_at.strftime("%A, %B %d at %I:%M %p")
        restaurant = user["restaurant_name"] or user["name"]
        sent_w = send_interview_scheduled_email(
            app_row["worker_email"], app_row["worker_name"], when, restaurant, app_row["title"],
        )
        sent_e = send_interview_scheduled_email(
            user["email"], user["name"], when, restaurant, app_row["title"],
        )
        email_sent = 1 if (sent_w or sent_e) else 0
    except Exception as e:
        log.warning("interview confirmation email failed: %s", e)

    db.execute(
        """INSERT INTO interviews (application_id, employer_id, worker_id, scheduled_at,
                                   google_event_id, calendar_invite_sent, confirmation_email_sent,
                                   worker_confirmed, employer_confirmed)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1)""",
        (app_id, user["id"], app_row["worker_id"], scheduled_at,
         google_event_id or None, 1 if google_event_id else 0, email_sent),
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
    _invalidate_all_sessions(user["id"])

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

    def _remove_files(paths):
        for p in paths:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except OSError as e:
                app.logger.warning("could not delete file %s: %s", p, e)

    try:
        if user["role"] == "employer":
            ev = db.execute(
                "SELECT business_license_path FROM employer_verifications WHERE employer_id = ?",
                (user_id,),
            ).fetchone()
            if ev:
                _remove_files([ev["business_license_path"]])
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
            v = db.execute(
                "SELECT id_document_path, selfie_path FROM verifications WHERE worker_id = ?",
                (user_id,),
            ).fetchone()
            if v:
                _remove_files([v["id_document_path"], v["selfie_path"]])
            # FK-safe deletion order:
            # referrals → interviews → applications → verifications
            db.execute("DELETE FROM referrals    WHERE worker_id = ?", (user_id,))
            db.execute("DELETE FROM interviews   WHERE worker_id = ?", (user_id,))
            db.execute("DELETE FROM applications WHERE worker_id = ?", (user_id,))
            db.execute("DELETE FROM verifications WHERE worker_id = ?", (user_id,))

        db.execute("DELETE FROM oauth_tokens WHERE user_id = ?", (user_id,))

        # Replace email with an untraceable placeholder — cannot set NULL because the
        # column has NOT NULL constraint, and UNIQUE means we need a distinct value per row.
        # All other PII columns are wiped outright.
        placeholder = f"deleted_{user_id}_{int(deletion_time.timestamp())}@deleted.invalid"
        db.execute(
            """UPDATE users SET
                 deleted_at = ?, email = ?, name = 'Deleted User', phone = NULL,
                 bio = NULL, languages_spoken = '', restaurant_name = NULL,
                 skills = '', availability = '', dialect_preference = '',
                 date_of_birth = NULL, us_state = NULL,
                 password_reset_token = NULL, password_reset_expiry = NULL,
                 email_verification_token = NULL
               WHERE id = ?""",
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

        frontend_url = os.environ.get("FRONTEND_URL", "https://entr.up.railway.app")
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


# ── Approximate location search (Step 4) ─────────────────────────────────────

_location_match_cache: dict = {}


def _haiku_location_match(query: str, locations: list[str]) -> dict:
    """
    Ask Haiku which stored job locations are within ~30 / ~60 miles of the
    searched location. Returns {location: {"miles": int, "within_30": bool}}.
    Results are cached per (query, locations-set).
    """
    import anthropic as _anthropic

    cache_key = (query.lower(), tuple(sorted(set(locations))))
    if cache_key in _location_match_cache:
        return _location_match_cache[cache_key]

    prompt = (
        "You are a US geography assistant. A job seeker searched for jobs near: "
        f"\"{query}\".\n\n"
        "Here are the locations of available jobs:\n"
        + "\n".join(f"- {loc}" for loc in set(locations) if loc)
        + "\n\nFor each job location, estimate the driving distance in miles from the "
        "searched location. Interpret abbreviations, misspellings, and neighborhoods "
        "sensibly (e.g. 'Greensboro' is near High Point, Burlington, Kernersville NC).\n\n"
        "Respond with ONLY a JSON object mapping each job location string EXACTLY as "
        "given to an integer estimated miles, like:\n"
        '{"High Point, NC": 18, "Charlotte, NC": 95}\n'
        "If a location is too vague to place, use 9999."
    )

    client = _anthropic.Anthropic()
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    distances = json.loads(text.strip())

    result = {}
    for loc, miles in distances.items():
        try:
            m = int(miles)
        except (TypeError, ValueError):
            m = 9999
        result[loc] = m
    _location_match_cache[cache_key] = result
    return result


@app.route("/api/worker/jobs/search")
@api_login_required(role="worker")
def api_worker_search_jobs():
    """
    Location-aware job search. ?location=Greensboro returns open jobs within
    ~30 miles (expanding to 60 if none), each with an approximate distance.
    """
    query = clean_text(request.args.get("location"), 120)
    db    = get_db()
    jobs  = db.execute(
        """SELECT j.*, u.name AS employer_name, u.restaurant_name
           FROM jobs j JOIN users u ON u.id = j.employer_id
           WHERE j.status = 'open'
           ORDER BY j.created_at DESC""",
    ).fetchall()
    jobs = [row_to_dict(j) for j in jobs]

    if not query:
        return jsonify({"jobs": jobs, "radius_miles": None, "expanded": False})

    if ai_rate_limited():
        return jsonify({"error": "Too many AI requests. Please wait a minute and try again."}), 429

    locations = [j["location"] for j in jobs if j.get("location")]
    if not locations:
        return jsonify({"jobs": [], "radius_miles": 30, "expanded": False,
                        "message": "No jobs have locations yet."})

    try:
        distances = _haiku_location_match(query, locations)
    except Exception as e:
        log.error("location search failed: %s", e)
        # Graceful fallback: plain substring match
        q = query.lower()
        matched = [j for j in jobs if j.get("location") and q in j["location"].lower()]
        return jsonify({"jobs": matched, "radius_miles": None, "expanded": False})

    def with_distance(max_miles: int):
        out = []
        for j in jobs:
            loc = j.get("location")
            if not loc:
                continue
            miles = distances.get(loc, 9999)
            if miles <= max_miles:
                item = dict(j)
                item["distance_miles"] = miles
                out.append(item)
        out.sort(key=lambda x: x["distance_miles"])
        return out

    within_30 = with_distance(30)
    if within_30:
        return jsonify({"jobs": within_30, "radius_miles": 30, "expanded": False})

    within_60 = with_distance(60)
    return jsonify({
        "jobs": within_60,
        "radius_miles": 60,
        "expanded": True,
        "message": "No jobs nearby — showing results within 60 miles",
    })


# ── Buddy chatbot (Step 5) ────────────────────────────────────────────────────

BUDDY_SYSTEM_PROMPT = """You are Buddy, a helpful assistant built into ENTR, a hiring platform for immigrant restaurant workers and owners.

Your job is to help users navigate and use the ENTR app. You can help with:
- How to post a job (for employers)
- How to apply to a job (for workers)
- How to verify identity
- How to schedule an interview
- How to use the translation feature
- How to contact an employer
- General questions about how ENTR works
- Translating any text the user needs help with

You must never:
- Recommend a specific job to a worker
- Tell someone which job is best for them
- Give career advice or hiring advice
- Answer questions unrelated to ENTR

Always respond in the same language the user writes in. Be warm, simple, and clear. Use short sentences. Avoid jargon.

The user's first message will be their language preference. From that point on, respond only in that language for the rest of the session.

If asked about anything outside of ENTR, say: "I can only help with questions about ENTR. What would you like to know?" """


@app.route("/api/buddy", methods=["POST"])
def api_buddy():
    """Stateless Buddy chat. Accepts {message, history:[{role,content}]}."""
    import anthropic as _anthropic

    if ai_rate_limited():
        return jsonify({"error": "Too many messages. Please wait a minute and try again."}), 429

    data    = request.get_json(force=True)
    message = clean_text(data.get("message"), 2000)
    history = data.get("history") or []

    if not message:
        return jsonify({"error": "Message is required"}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        return jsonify({"error": "Buddy is not available right now."}), 503

    # Rebuild the session-only conversation (cap at last 20 turns, sanitize)
    messages = []
    for turn in history[-20:]:
        role = turn.get("role")
        content = clean_text(turn.get("content"), 2000)
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    try:
        client = _anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=BUDDY_SYSTEM_PROMPT,
            messages=messages,
        )
        reply = resp.content[0].text.strip()
        return jsonify({"reply": reply})
    except Exception as e:
        log.error("buddy error: %s: %s", type(e).__name__, e)
        return jsonify({"error": "Buddy could not answer right now. Please try again."}), 500


# ── Google Calendar OAuth (Step 6) ────────────────────────────────────────────

def _get_oauth_token(user_id: int):
    return get_db().execute(
        "SELECT * FROM oauth_tokens WHERE user_id = ? AND provider = 'google'", (user_id,)
    ).fetchone()


def _backend_url() -> str:
    return os.environ.get("BACKEND_URL", "https://entr-production.up.railway.app").rstrip("/")


@app.route("/api/calendar/status")
@api_login_required()
def api_calendar_status():
    from google_calendar import oauth_configured
    user  = get_current_user()
    token = _get_oauth_token(user["id"])
    return jsonify({
        "oauth_available": oauth_configured(),
        "connected": bool(token and token["refresh_token"]),
    })


@app.route("/api/calendar/connect")
@api_login_required()
def api_calendar_connect():
    """Start the Google OAuth flow; returns the URL to redirect the user to."""
    from google_calendar import get_oauth_flow
    flow = get_oauth_flow(f"{_backend_url()}/api/calendar/callback")
    if not flow:
        return jsonify({"error": "Google Calendar is not configured on the server."}), 503
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent",
    )
    session["gcal_oauth_state"] = state
    return jsonify({"auth_url": auth_url})


@app.route("/api/calendar/callback")
def api_calendar_callback():
    """OAuth redirect target. Stores tokens then bounces back to the frontend."""
    from google_calendar import get_oauth_flow
    frontend = os.environ.get("FRONTEND_URL", "https://entr.up.railway.app").rstrip("/")

    user = get_current_user()
    if not user:
        return redirect(f"{frontend}/login")

    flow = get_oauth_flow(f"{_backend_url()}/api/calendar/callback")
    if not flow:
        return redirect(frontend)

    try:
        flow.fetch_token(authorization_response=request.url.replace("http://", "https://", 1)
                         if request.url.startswith("http://") else request.url)
        creds = flow.credentials
        db = get_db()
        db.execute(
            """INSERT INTO oauth_tokens (user_id, provider, access_token, refresh_token, token_expiry)
               VALUES (?, 'google', ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 access_token=excluded.access_token,
                 refresh_token=COALESCE(excluded.refresh_token, oauth_tokens.refresh_token),
                 token_expiry=excluded.token_expiry""",
            (user["id"], creds.token, creds.refresh_token,
             creds.expiry.isoformat() if creds.expiry else None),
        )
        db.commit()
    except Exception as e:
        log.error("calendar oauth callback failed: %s", e)

    dest = "/employer/dashboard" if user["role"] == "employer" else "/worker/dashboard"
    return redirect(f"{frontend}{dest}?calendar=connected")


@app.route("/api/calendar/disconnect", methods=["POST"])
@api_login_required()
def api_calendar_disconnect():
    user = get_current_user()
    db = get_db()
    db.execute("DELETE FROM oauth_tokens WHERE user_id = ?", (user["id"],))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/employer/applications/<int:app_id>/suggest-slots")
@api_login_required(role="employer")
def api_suggest_interview_slots(app_id):
    """
    Suggest 3 interview times that work for both parties.
    Uses Google free/busy when both calendars are connected; otherwise returns
    {slots: null} so the frontend falls back to the manual date/time form.
    """
    from google_calendar import suggest_slots
    user = get_current_user()
    db   = get_db()

    app_row = db.execute(
        """SELECT a.*, j.employer_id FROM applications a
           JOIN jobs j ON j.id = a.job_id WHERE a.id = ?""",
        (app_id,),
    ).fetchone()
    if not app_row or app_row["employer_id"] != user["id"]:
        return jsonify({"error": "Application not found"}), 404

    emp_token = _get_oauth_token(user["id"])
    wrk_token = _get_oauth_token(app_row["worker_id"])

    slots = None
    if emp_token and wrk_token:
        slots = suggest_slots(emp_token, wrk_token, count=3)

    # Include the worker's manually-entered availability for the fallback UI
    availability = None
    if app_row["worker_availability"]:
        try:
            availability = json.loads(app_row["worker_availability"])
        except json.JSONDecodeError:
            pass

    return jsonify({
        "slots": slots,
        "worker_availability": availability,
        "both_connected": bool(emp_token and wrk_token),
    })


def _job_contact_info(job_row) -> str:
    """Human-readable contact summary for calendar event descriptions."""
    parts = []
    labels = {
        "contact_phone": "Phone", "contact_whatsapp": "WhatsApp",
        "contact_wechat": "WeChat", "contact_line": "Line",
        "contact_gchat": "Google Chat/Gmail",
    }
    for col, label in labels.items():
        try:
            val = job_row[col]
        except (IndexError, KeyError):
            val = None
        if val:
            parts.append(f"{label}: {val}")
    return " | ".join(parts)


@app.route("/api/employer/applications/<int:app_id>/propose-interview", methods=["POST"])
@api_login_required(role="employer")
def api_propose_interview(app_id):
    """
    Employer proposes an interview time (one of the suggested slots).
    The worker is notified and must confirm before calendar events are created.
    """
    user = get_current_user()
    db   = get_db()

    app_row = db.execute(
        """SELECT a.*, j.employer_id, j.title, u.name AS worker_name,
                  u.email AS worker_email, u.language_pref AS worker_lang
           FROM applications a
           JOIN jobs j ON j.id = a.job_id
           JOIN users u ON u.id = a.worker_id
           WHERE a.id = ?""",
        (app_id,),
    ).fetchone()
    if not app_row or app_row["employer_id"] != user["id"]:
        return jsonify({"error": "Application not found"}), 404

    existing = db.execute(
        "SELECT * FROM interviews WHERE application_id = ?", (app_id,)
    ).fetchone()
    if existing and existing["status"] == "scheduled":
        return jsonify({"error": "An interview is already proposed or scheduled for this application"}), 409

    data = request.get_json(force=True)
    scheduled_at_str = data.get("scheduled_at")
    if not scheduled_at_str:
        return jsonify({"error": "scheduled_at is required"}), 400
    try:
        scheduled_at = _to_naive_utc(datetime.fromisoformat(scheduled_at_str.replace("Z", "+00:00")))
    except (ValueError, AttributeError):
        return jsonify({"error": "Invalid date format"}), 400

    if existing:
        db.execute(
            """UPDATE interviews SET scheduled_at=?, status='scheduled',
                   worker_confirmed=0, employer_confirmed=1,
                   google_event_id=NULL, calendar_invite_sent=0
               WHERE application_id=?""",
            (scheduled_at, app_id),
        )
    else:
        db.execute(
            """INSERT INTO interviews (application_id, employer_id, worker_id, scheduled_at,
                                       worker_confirmed, employer_confirmed)
               VALUES (?, ?, ?, ?, 0, 1)""",
            (app_id, user["id"], app_row["worker_id"], scheduled_at),
        )
    db.commit()

    # Notify the worker to confirm
    try:
        from email_service import send_interview_proposal_email
        when = scheduled_at.strftime("%A, %B %d at %I:%M %p")
        send_interview_proposal_email(
            app_row["worker_email"], app_row["worker_name"], when,
            user["restaurant_name"] or user["name"], app_row["title"],
            app_row["worker_lang"] or "en",
        )
    except Exception as e:
        log.warning("interview proposal email failed: %s", e)

    interview = db.execute(
        "SELECT * FROM interviews WHERE application_id = ?", (app_id,)
    ).fetchone()
    return jsonify({"interview": row_to_dict(interview)}), 201


@app.route("/api/worker/interviews/<int:interview_id>/confirm", methods=["POST"])
@api_login_required(role="worker")
def api_worker_confirm_interview(interview_id):
    """
    Worker confirms a proposed interview. Creates the calendar event on both
    calendars (when connected) and emails a confirmation to both parties.
    """
    user = get_current_user()
    db   = get_db()

    interview = db.execute(
        """SELECT i.*, a.job_id, j.title, j.contact_phone, j.contact_whatsapp,
                  j.contact_wechat, j.contact_line, j.contact_gchat,
                  e.name AS employer_name, e.email AS employer_email,
                  e.restaurant_name
           FROM interviews i
           JOIN applications a ON a.id = i.application_id
           JOIN jobs j ON j.id = a.job_id
           JOIN users e ON e.id = i.employer_id
           WHERE i.id = ? AND i.worker_id = ?""",
        (interview_id, user["id"]),
    ).fetchone()
    if not interview:
        return jsonify({"error": "Interview not found"}), 404
    if interview["worker_confirmed"]:
        return jsonify({"error": "Interview already confirmed"}), 409

    scheduled_at = interview["scheduled_at"]
    if isinstance(scheduled_at, str):
        scheduled_at = _to_naive_utc(datetime.fromisoformat(scheduled_at.replace("Z", "+00:00")))

    from google_calendar import create_interview_event
    google_event_id = create_interview_event(
        employer_email=interview["employer_email"],
        worker_email=user["email"],
        scheduled_at=scheduled_at,
        job_title=interview["title"],
        restaurant_name=interview["restaurant_name"] or interview["employer_name"],
        worker_name=user["name"],
        worker_language=user["language_pref"] or "en",
        employer_token_row=_get_oauth_token(interview["employer_id"]),
        worker_token_row=_get_oauth_token(user["id"]),
        contact_info=_job_contact_info(interview),
    )

    db.execute(
        """UPDATE interviews SET worker_confirmed=1,
               google_event_id=?, calendar_invite_sent=?
           WHERE id=?""",
        (google_event_id or None, 1 if google_event_id else 0, interview_id),
    )
    db.execute(
        "UPDATE applications SET status='interview_scheduled' WHERE id=?",
        (interview["application_id"],),
    )
    db.commit()

    # Confirmation emails to both parties
    email_sent = 0
    try:
        from email_service import send_interview_scheduled_email
        when = scheduled_at.strftime("%A, %B %d at %I:%M %p")
        restaurant = interview["restaurant_name"] or interview["employer_name"]
        sent_w = send_interview_scheduled_email(
            user["email"], user["name"], when, restaurant, interview["title"],
            user["language_pref"] or "en",
        )
        sent_e = send_interview_scheduled_email(
            interview["employer_email"], interview["employer_name"], when,
            restaurant, interview["title"],
        )
        email_sent = 1 if (sent_w or sent_e) else 0
    except Exception as e:
        log.warning("interview confirmation email failed: %s", e)

    if email_sent:
        db.execute(
            "UPDATE interviews SET confirmation_email_sent=1 WHERE id=?", (interview_id,)
        )
        db.commit()

    updated = db.execute("SELECT * FROM interviews WHERE id=?", (interview_id,)).fetchone()
    return jsonify({"interview": row_to_dict(updated), "calendar_event_created": bool(google_event_id)})


# ── GDPR / CCPA compliance (Step 7) ───────────────────────────────────────────

@app.route("/api/user/export")
@api_login_required()
def api_export_data():
    """Export all of the user's data as JSON (GDPR right to portability)."""
    user = get_current_user()
    db   = get_db()
    uid  = user["id"]

    out = {"exported_at": datetime.utcnow().isoformat() + "Z"}

    u = row_to_dict(user)
    u.pop("password_hash", None)
    u.pop("email_verification_token", None)
    u.pop("password_reset_token", None)
    out["account"] = u

    if user["role"] == "worker":
        out["applications"] = [row_to_dict(r) for r in db.execute(
            "SELECT * FROM applications WHERE worker_id = ?", (uid,)).fetchall()]
        v = db.execute("SELECT * FROM verifications WHERE worker_id = ?", (uid,)).fetchone()
        out["verification"] = row_to_dict(v)
        out["interviews"] = [row_to_dict(r) for r in db.execute(
            "SELECT * FROM interviews WHERE worker_id = ?", (uid,)).fetchall()]
        out["referrals"] = [row_to_dict(r) for r in db.execute(
            "SELECT * FROM referrals WHERE worker_id = ?", (uid,)).fetchall()]
    else:
        out["jobs"] = [row_to_dict(r) for r in db.execute(
            "SELECT * FROM jobs WHERE employer_id = ?", (uid,)).fetchall()]
        ev = db.execute("SELECT * FROM employer_verifications WHERE employer_id = ?", (uid,)).fetchone()
        out["business_verification"] = row_to_dict(ev)
        out["interviews"] = [row_to_dict(r) for r in db.execute(
            "SELECT * FROM interviews WHERE employer_id = ?", (uid,)).fetchall()]
        out["referrals_made"] = [row_to_dict(r) for r in db.execute(
            "SELECT * FROM referrals WHERE referring_employer_id = ?", (uid,)).fetchall()]

    resp = jsonify(out)
    resp.headers["Content-Disposition"] = "attachment; filename=entr-data-export.json"
    return resp


@app.route("/api/account", methods=["DELETE"])
@api_login_required()
def api_delete_account_rest():
    """GDPR right-to-erasure endpoint. Same behavior as POST /api/user/delete-account."""
    return api_delete_account()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
