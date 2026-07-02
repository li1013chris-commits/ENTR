"""
Google Calendar integration for interview scheduling.

Two modes:
  1. Per-user OAuth (preferred): employer and worker each connect their Google
     Calendar. We read free/busy from both, suggest overlapping slots, and
     create the event on both calendars.
  2. Service-account fallback (legacy): a single ENTR calendar invites both
     parties by email.

If neither is configured, callers fall back to plain confirmation emails.

Required env vars for OAuth:
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, BACKEND_URL (for the redirect URI)
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as UserCredentials
from google.auth.exceptions import GoogleAuthError
import googleapiclient.discovery as discovery

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_TZ = os.environ.get("INTERVIEW_TIMEZONE", "America/New_York")


# ── OAuth helpers ─────────────────────────────────────────────────────────────

def oauth_configured() -> bool:
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


def get_oauth_flow(redirect_uri: str):
    """Build an OAuth flow from env vars. Returns None if not configured."""
    if not oauth_configured():
        return None
    from google_auth_oauthlib.flow import Flow
    client_config = {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)


def _user_credentials(token_row) -> UserCredentials | None:
    """Build refreshable user credentials from an oauth_tokens DB row."""
    if not token_row or not token_row["refresh_token"]:
        return None
    try:
        creds = UserCredentials(
            token=token_row["access_token"],
            refresh_token=token_row["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ.get("GOOGLE_CLIENT_ID"),
            client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
            scopes=SCOPES,
        )
        if not creds.valid:
            creds.refresh(GoogleRequest())
        return creds
    except Exception as e:
        log.warning("could not build/refresh user credentials: %s", e)
        return None


def _user_service(token_row):
    creds = _user_credentials(token_row)
    if not creds:
        return None
    try:
        return discovery.build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        log.error("failed to build calendar service: %s", e)
        return None


def _service_account_service():
    """Legacy service-account mode via GOOGLE_CALENDAR_CREDENTIALS JSON."""
    creds_json = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS")
    if not creds_json:
        return None
    try:
        creds_dict = json.loads(creds_json)
        credentials = ServiceAccountCredentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return discovery.build("calendar", "v3", credentials=credentials, cache_discovery=False)
    except (json.JSONDecodeError, GoogleAuthError, Exception) as e:
        log.error("Failed to initialize service-account calendar: %s", e)
        return None


# ── Free/busy + slot suggestion ───────────────────────────────────────────────

def _busy_windows(service, days_ahead: int = 7):
    """Return list of (start, end) datetimes the user is busy in the next N days."""
    now = datetime.now(timezone.utc)
    body = {
        "timeMin": now.isoformat(),
        "timeMax": (now + timedelta(days=days_ahead)).isoformat(),
        "items": [{"id": "primary"}],
    }
    resp = service.freebusy().query(body=body).execute()
    windows = []
    for b in resp.get("calendars", {}).get("primary", {}).get("busy", []):
        windows.append((
            datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
            datetime.fromisoformat(b["end"].replace("Z", "+00:00")),
        ))
    return windows


def _is_free(slot_start: datetime, slot_end: datetime, busy: list) -> bool:
    return all(slot_end <= b_start or slot_start >= b_end for b_start, b_end in busy)


def suggest_slots(employer_token_row, worker_token_row, count: int = 3,
                  duration_minutes: int = 60) -> list[str] | None:
    """
    Find `count` upcoming 1-hour slots (9am-6pm UTC-4-ish business window, next
    7 days) where both parties are free. Returns ISO strings, or None if either
    party has no connected calendar.
    """
    emp_service = _user_service(employer_token_row)
    wrk_service = _user_service(worker_token_row)
    if not emp_service or not wrk_service:
        return None

    try:
        emp_busy = _busy_windows(emp_service)
        wrk_busy = _busy_windows(wrk_service)
    except Exception as e:
        log.error("freebusy lookup failed: %s", e)
        return None

    slots = []
    now = datetime.now(timezone.utc)
    # Start from the next full hour, at least 4h out
    cursor = (now + timedelta(hours=4)).replace(minute=0, second=0, microsecond=0)
    end_search = now + timedelta(days=7)

    while cursor < end_search and len(slots) < count:
        # Business hours: 13:00-22:00 UTC covers 9am-6pm US Eastern
        if 13 <= cursor.hour < 22:
            slot_end = cursor + timedelta(minutes=duration_minutes)
            if _is_free(cursor, slot_end, emp_busy) and _is_free(cursor, slot_end, wrk_busy):
                slots.append(cursor.isoformat())
        cursor += timedelta(hours=1)

    return slots


# ── Event creation ────────────────────────────────────────────────────────────

def _build_event_body(scheduled_at: datetime, job_title: str, restaurant_name: str,
                      worker_name: str, employer_email: str, worker_email: str,
                      contact_info: str = "", worker_language: str = "en") -> dict:
    lang_names = {
        "es": "Entrevista", "zh": "面试", "fr": "Entretien",
        "pt": "Entrevista", "vi": "Phỏng vấn",
    }
    event_type = lang_names.get(worker_language, "Interview")
    title = f"Interview - {job_title} | {event_type} - {job_title}"

    description = (
        f"ENTR Interview\n\n"
        f"Position: {job_title}\n"
        f"Restaurant: {restaurant_name}\n"
        f"Worker: {worker_name}\n"
        f"Employer contact: {employer_email}\n"
        f"Worker contact: {worker_email}\n"
    )
    if contact_info:
        description += f"Other contact info: {contact_info}\n"
    description += "\nThis interview was scheduled through ENTR (entr.up.railway.app)."

    end_at = scheduled_at + timedelta(hours=1)
    return {
        "summary": title,
        "description": description,
        "start": {"dateTime": scheduled_at.isoformat(), "timeZone": DEFAULT_TZ},
        "end":   {"dateTime": end_at.isoformat(),       "timeZone": DEFAULT_TZ},
        "attendees": [
            {"email": employer_email},
            {"email": worker_email},
        ],
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},
                {"method": "popup", "minutes": 30},
            ],
        },
    }


def create_interview_event(
    employer_email: str,
    worker_email: str,
    scheduled_at: datetime,
    job_title: str,
    restaurant_name: str,
    worker_name: str,
    worker_language: str = "en",
    employer_token_row=None,
    worker_token_row=None,
    contact_info: str = "",
) -> str | None:
    """
    Create the interview event.
    Preferred: on the employer's own calendar (attendee invite reaches the
    worker). If the worker also connected OAuth, insert on their calendar too.
    Fallback: legacy service account. Returns the primary event ID or None.
    """
    body = _build_event_body(
        scheduled_at, job_title, restaurant_name, worker_name,
        employer_email, worker_email, contact_info, worker_language,
    )

    event_id = None

    # 1. Employer's own calendar (invites the worker by email)
    emp_service = _user_service(employer_token_row) if employer_token_row else None
    if emp_service:
        try:
            created = emp_service.events().insert(
                calendarId="primary", body=body, sendUpdates="all",
            ).execute()
            event_id = created.get("id")
            log.info("Created calendar event %s on employer calendar", event_id)
        except Exception as e:
            log.error("employer-calendar event creation failed: %s", e)

    # 2. Worker's own calendar (guarantees it shows even if invite is missed)
    wrk_service = _user_service(worker_token_row) if worker_token_row else None
    if wrk_service:
        try:
            created = wrk_service.events().insert(
                calendarId="primary", body=body, sendUpdates="none",
            ).execute()
            event_id = event_id or created.get("id")
            log.info("Created calendar event on worker calendar")
        except Exception as e:
            log.error("worker-calendar event creation failed: %s", e)

    if event_id:
        return event_id

    # 3. Legacy service-account fallback
    service = _service_account_service()
    if not service:
        log.warning("No Google Calendar integration available")
        return None
    try:
        created = service.events().insert(
            calendarId="primary", body=body, sendUpdates="all",
        ).execute()
        log.info("Created calendar event %s via service account", created.get("id"))
        return created.get("id")
    except Exception as e:
        log.error("Failed to create calendar event: %s", e)
        return None
