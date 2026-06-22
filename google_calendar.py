import os
import json
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from google.auth.exceptions import GoogleAuthError
import googleapiclient.discovery as discovery
import logging

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_calendar_service():
    """Authenticate with Google Calendar API using service account credentials."""
    creds_json = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS")
    if not creds_json:
        log.warning("GOOGLE_CALENDAR_CREDENTIALS not set")
        return None

    try:
        creds_dict = json.loads(creds_json)
        credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        service = discovery.build("calendar", "v3", credentials=credentials)
        return service
    except (json.JSONDecodeError, GoogleAuthError, Exception) as e:
        log.error(f"Failed to initialize Google Calendar service: {e}")
        return None


def create_interview_event(
    employer_email: str,
    worker_email: str,
    scheduled_at: datetime,
    job_title: str,
    restaurant_name: str,
    worker_name: str,
    worker_language: str = "en",
) -> str | None:
    """
    Create a Google Calendar event for both parties.
    Returns the Google Event ID if successful, None otherwise.
    """
    service = _get_calendar_service()
    if not service:
        log.warning("Google Calendar service not available")
        return None

    try:
        # Prepare event details in both English and worker's language
        lang_names = {
            "es": "Entrevista",
            "zh": "面试",
            "fr": "Entretien",
            "pt": "Entrevista",
            "vi": "Phỏng vấn",
        }
        event_type = lang_names.get(worker_language, "Interview")

        # Event title bilingual
        title = f"Interview - {job_title} | {event_type} - {job_title}"

        # Description bilingual with key info
        description = f"""ENTR Interview - {restaurant_name}
Position: {job_title}
Worker: {worker_name}

---

This interview was scheduled through ENTR.

---

ENTREVISTA ENTR - {restaurant_name}
Posicion: {job_title}
Trabajador: {worker_name}

Esta entrevista fue programada a traves de ENTR."""

        event = {
            "summary": title,
            "description": description,
            "start": {
                "dateTime": scheduled_at.isoformat(),
                "timeZone": "America/New_York",
            },
            "end": {
                "dateTime": (datetime.fromisoformat(str(scheduled_at.isoformat())).replace(
                    hour=scheduled_at.hour + 1
                )).isoformat() if hasattr(scheduled_at, 'replace') else scheduled_at,
                "timeZone": "America/New_York",
            },
            "attendees": [
                {"email": employer_email, "responseStatus": "accepted"},
                {"email": worker_email, "responseStatus": "needsAction"},
            ],
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 24 * 60},
                    {"method": "notification", "minutes": 30},
                ],
            },
        }

        created_event = service.events().insert(
            calendarId="primary",
            body=event,
            sendUpdates="all",
        ).execute()

        log.info(f"Created calendar event {created_event['id']}")
        return created_event.get("id")

    except Exception as e:
        log.error(f"Failed to create calendar event: {e}")
        return None
