import sqlite3
import os
from flask import g

DATABASE = os.environ.get("DATABASE_PATH", "entr.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA busy_timeout=5000")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _migrate(conn):
    """Add new columns / tables to existing databases without destroying data."""
    cursor = conn.cursor()

    def cols(table):
        return {row[1] for row in cursor.execute(f"PRAGMA table_info({table})")}

    def tables():
        return {row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    def add(table, column, typedef):
        if column not in cols(table):
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {typedef}")

    # verifications: old schema used user_id; new schema uses worker_id.
    ver_cols = cols("verifications")
    if "user_id" in ver_cols and "worker_id" not in ver_cols:
        cursor.executescript("""
            CREATE TABLE verifications_new (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id           INTEGER NOT NULL UNIQUE REFERENCES users(id),
                id_document_path    TEXT,
                selfie_path         TEXT,
                extracted_dob       TEXT,
                extracted_name      TEXT,
                face_match_score    REAL,
                age_verified        INTEGER DEFAULT 0,
                identity_verified   INTEGER DEFAULT 0,
                verification_status TEXT DEFAULT 'pending'
                    CHECK(verification_status IN ('pending','verified','failed','flagged')),
                verified_at         TIMESTAMP,
                failure_reason      TEXT,
                created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO verifications_new (id, worker_id, created_at)
                SELECT id, user_id, created_at FROM verifications;
            DROP TABLE verifications;
            ALTER TABLE verifications_new RENAME TO verifications;
        """)
    elif "worker_id" in ver_cols:
        for col, typedef in [
            ("id_document_path",  "TEXT"),
            ("selfie_path",       "TEXT"),
            ("extracted_dob",     "TEXT"),
            ("extracted_name",    "TEXT"),
            ("face_match_score",  "REAL"),
            ("age_verified",      "INTEGER DEFAULT 0"),
            ("identity_verified", "INTEGER DEFAULT 0"),
            ("verification_status", "TEXT DEFAULT 'pending'"),
            ("verified_at",       "TIMESTAMP"),
            ("failure_reason",    "TEXT"),
        ]:
            add("verifications", col, typedef)

    # applications: add 'hired' status and interview availability
    apps_schema = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='applications'"
    ).fetchone()
    if apps_schema:
        needs_hired = "'hired'" not in apps_schema[0]
        needs_availability = "worker_availability" not in {row[1] for row in cursor.execute("PRAGMA table_info(applications)")}

        if needs_hired or needs_availability:
            cursor.executescript("""
                CREATE TABLE applications_new (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id                INTEGER NOT NULL REFERENCES jobs(id),
                    worker_id             INTEGER NOT NULL REFERENCES users(id),
                    cover_letter          TEXT,
                    ai_score              INTEGER,
                    ai_summary            TEXT,
                    worker_availability   TEXT,
                    status                TEXT DEFAULT 'pending'
                        CHECK(status IN ('pending','reviewed','accepted','rejected','hired','interview_scheduled')),
                    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(job_id, worker_id)
                );
                INSERT INTO applications_new SELECT
                    id, job_id, worker_id, cover_letter, ai_score, ai_summary,
                    NULL, status, created_at
                FROM applications;
                DROP TABLE applications;
                ALTER TABLE applications_new RENAME TO applications;
            """)
        else:
            add("applications", "worker_availability", "TEXT")
            add_status = cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='applications'"
            ).fetchone()
            if add_status and "'interview_scheduled'" not in add_status[0]:
                cursor.executescript("""
                    CREATE TABLE applications_new (
                        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id                INTEGER NOT NULL REFERENCES jobs(id),
                        worker_id             INTEGER NOT NULL REFERENCES users(id),
                        cover_letter          TEXT,
                        ai_score              INTEGER,
                        ai_summary            TEXT,
                        worker_availability   TEXT,
                        status                TEXT DEFAULT 'pending'
                            CHECK(status IN ('pending','reviewed','accepted','rejected','hired','interview_scheduled')),
                        created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(job_id, worker_id)
                    );
                    INSERT INTO applications_new SELECT * FROM applications;
                    DROP TABLE applications;
                    ALTER TABLE applications_new RENAME TO applications;
                """)

    # users: add email verification columns
    for col, typedef in [
        ("email_verified",            "INTEGER DEFAULT 0"),
        ("email_verification_token",  "TEXT"),
    ]:
        add("users", col, typedef)

    # users: add new worker profile fields
    for col, typedef in [
        ("skills",              "TEXT DEFAULT ''"),
        ("availability",        "TEXT DEFAULT ''"),
        ("dialect_preference",  "TEXT DEFAULT ''"),
        ("password_reset_token", "TEXT"),
        ("password_reset_expiry", "TIMESTAMP"),
        ("deleted_at",          "TIMESTAMP"),
    ]:
        add("users", col, typedef)

    # jobs: add expiry field
    add("jobs", "expires_at", "TIMESTAMP")

    # jobs: structured pay + skills/info + contact methods (Steps 2-3)
    for col, typedef in [
        ("pay_amount",       "TEXT"),
        ("pay_type",         "TEXT"),
        ("tips_included",    "INTEGER DEFAULT 0"),
        ("skills_text",      "TEXT"),
        ("additional_info",  "TEXT"),
        ("contact_phone",    "TEXT"),
        ("contact_whatsapp", "TEXT"),
        ("contact_wechat",   "TEXT"),
        ("contact_line",     "TEXT"),
        ("contact_gchat",    "TEXT"),
    ]:
        add("jobs", col, typedef)

    # users: compliance fields (Step 7)
    for col, typedef in [
        ("date_of_birth",   "TEXT"),
        ("us_state",        "TEXT"),
        ("tos_accepted_at", "TIMESTAMP"),
    ]:
        add("users", col, typedef)

    # Google Calendar OAuth tokens (Step 6)
    if "oauth_tokens" not in tables():
        cursor.execute("""
            CREATE TABLE oauth_tokens (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL UNIQUE REFERENCES users(id),
                provider      TEXT NOT NULL DEFAULT 'google',
                access_token  TEXT,
                refresh_token TEXT,
                token_expiry  TIMESTAMP,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # interviews: proposed slots + confirmations (Step 6)
    for col, typedef in [
        ("proposed_slots",     "TEXT"),
        ("worker_confirmed",   "INTEGER DEFAULT 0"),
        ("employer_confirmed", "INTEGER DEFAULT 0"),
    ]:
        add("interviews", col, typedef)

    # employer_verifications table
    if "employer_verifications" not in tables():
        cursor.execute("""
            CREATE TABLE employer_verifications (
                id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                employer_id                 INTEGER NOT NULL UNIQUE REFERENCES users(id),
                business_license_path       TEXT,
                business_name_entered       TEXT,
                address_entered             TEXT,
                extracted_business_name     TEXT,
                extracted_address           TEXT,
                document_type               TEXT,
                match_confidence            REAL,
                business_verified           INTEGER DEFAULT 0,
                business_verification_status TEXT DEFAULT 'pending'
                    CHECK(business_verification_status IN ('pending','verified','failed')),
                verified_at                 TIMESTAMP,
                failure_reason              TEXT,
                created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # referrals table
    if "referrals" not in tables():
        cursor.execute("""
            CREATE TABLE referrals (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                referring_employer_id INTEGER NOT NULL REFERENCES users(id),
                worker_id             INTEGER NOT NULL REFERENCES users(id),
                job_application_id    INTEGER NOT NULL REFERENCES applications(id),
                referral_note         TEXT,
                status                TEXT DEFAULT 'active'
                    CHECK(status IN ('active','revoked')),
                created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(referring_employer_id, worker_id, job_application_id)
            )
        """)

    # interviews table
    if "interviews" not in tables():
        cursor.execute("""
            CREATE TABLE interviews (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id          INTEGER NOT NULL UNIQUE REFERENCES applications(id),
                employer_id             INTEGER NOT NULL REFERENCES users(id),
                worker_id               INTEGER NOT NULL REFERENCES users(id),
                scheduled_at            TIMESTAMP NOT NULL,
                google_event_id         TEXT,
                status                  TEXT DEFAULT 'scheduled'
                    CHECK(status IN ('scheduled','completed','cancelled')),
                calendar_invite_sent    INTEGER DEFAULT 0,
                confirmation_email_sent INTEGER DEFAULT 0,
                created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    conn.commit()


def init_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email           TEXT UNIQUE NOT NULL,
            password_hash   TEXT NOT NULL,
            role            TEXT NOT NULL CHECK(role IN ('employer','worker')),
            name            TEXT NOT NULL,
            phone           TEXT,
            language_pref   TEXT DEFAULT 'en',
            bio             TEXT,
            experience_years INTEGER DEFAULT 0,
            languages_spoken TEXT DEFAULT '',
            restaurant_name TEXT,
            email_verified            INTEGER DEFAULT 0,
            email_verification_token  TEXT,
            skills              TEXT DEFAULT '',
            availability        TEXT DEFAULT '',
            dialect_preference  TEXT DEFAULT '',
            password_reset_token  TEXT,
            password_reset_expiry TIMESTAMP,
            deleted_at          TIMESTAMP,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            employer_id         INTEGER NOT NULL REFERENCES users(id),
            title               TEXT NOT NULL,
            description         TEXT,
            pay                 TEXT NOT NULL,
            hours               TEXT NOT NULL,
            experience_required INTEGER DEFAULT 0,
            language_preference TEXT DEFAULT '',
            location            TEXT,
            status              TEXT DEFAULT 'open' CHECK(status IN ('open','closed')),
            expires_at          TIMESTAMP,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS applications (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id                INTEGER NOT NULL REFERENCES jobs(id),
            worker_id             INTEGER NOT NULL REFERENCES users(id),
            cover_letter          TEXT,
            ai_score              INTEGER,
            ai_summary            TEXT,
            worker_availability   TEXT,
            status                TEXT DEFAULT 'pending'
                CHECK(status IN ('pending','reviewed','accepted','rejected','hired','interview_scheduled')),
            created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(job_id, worker_id)
        );

        CREATE TABLE IF NOT EXISTS verifications (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id           INTEGER NOT NULL UNIQUE REFERENCES users(id),
            id_document_path    TEXT,
            selfie_path         TEXT,
            extracted_dob       TEXT,
            extracted_name      TEXT,
            face_match_score    REAL,
            age_verified        INTEGER DEFAULT 0,
            identity_verified   INTEGER DEFAULT 0,
            verification_status TEXT DEFAULT 'pending'
                CHECK(verification_status IN ('pending','verified','failed','flagged')),
            verified_at         TIMESTAMP,
            failure_reason      TEXT,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS employer_verifications (
            id                           INTEGER PRIMARY KEY AUTOINCREMENT,
            employer_id                  INTEGER NOT NULL UNIQUE REFERENCES users(id),
            business_license_path        TEXT,
            business_name_entered        TEXT,
            address_entered              TEXT,
            extracted_business_name      TEXT,
            extracted_address            TEXT,
            document_type                TEXT,
            match_confidence             REAL,
            business_verified            INTEGER DEFAULT 0,
            business_verification_status TEXT DEFAULT 'pending'
                CHECK(business_verification_status IN ('pending','verified','failed')),
            verified_at                  TIMESTAMP,
            failure_reason               TEXT,
            created_at                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS referrals (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            referring_employer_id INTEGER NOT NULL REFERENCES users(id),
            worker_id             INTEGER NOT NULL REFERENCES users(id),
            job_application_id    INTEGER NOT NULL REFERENCES applications(id),
            referral_note         TEXT,
            status                TEXT DEFAULT 'active'
                CHECK(status IN ('active','revoked')),
            created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(referring_employer_id, worker_id, job_application_id)
        );

        CREATE TABLE IF NOT EXISTS interviews (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id          INTEGER NOT NULL UNIQUE REFERENCES applications(id),
            employer_id             INTEGER NOT NULL REFERENCES users(id),
            worker_id               INTEGER NOT NULL REFERENCES users(id),
            scheduled_at            TIMESTAMP NOT NULL,
            google_event_id         TEXT,
            status                  TEXT DEFAULT 'scheduled'
                CHECK(status IN ('scheduled','completed','cancelled')),
            calendar_invite_sent    INTEGER DEFAULT 0,
            confirmation_email_sent INTEGER DEFAULT 0,
            created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    _migrate(conn)
    conn.close()
