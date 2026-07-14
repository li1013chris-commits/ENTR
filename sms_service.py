"""SMS service for ENTR.

Text messages go out through Brevo's transactional SMS HTTP API
(POST /v3/transactionalSMS/sms) using the same BREVO_API_KEY as email.
If the key is not set, messages are logged to the console instead so the
flow can still be exercised in development.
"""

import os
import logging

import requests

log = logging.getLogger(__name__)

BREVO_SMS_URL = "https://api.brevo.com/v3/transactionalSMS/sms"
# Brevo SMS sender: max 11 alphanumeric chars
SMS_SENDER = os.environ.get("BREVO_SMS_SENDER", "ENTR")


def send_sms(to_phone: str, content: str) -> bool:
    """Send an SMS via Brevo; logs to console if no API key is configured."""
    api_key = os.environ.get("BREVO_API_KEY", "")
    if not api_key:
        log.info(f"BREVO_API_KEY not configured. SMS:\nTo: {to_phone}\n\n{content}")
        return False

    payload = {
        "type": "transactional",
        "sender": SMS_SENDER,
        "recipient": to_phone,
        "content": content,
    }
    try:
        resp = requests.post(
            BREVO_SMS_URL,
            json=payload,
            headers={
                "api-key": api_key,
                "accept": "application/json",
                "content-type": "application/json",
            },
            timeout=15,
        )
        if 200 <= resp.status_code < 300:
            log.info(f"SMS sent via Brevo to {to_phone}")
            return True
        log.error(f"Brevo SMS failed ({resp.status_code}) to {to_phone}: {resp.text[:300]}")
        return False
    except requests.RequestException as e:
        log.error(f"Brevo SMS request error sending to {to_phone}: {e}")
        return False


def send_otp_sms(to_phone: str, code: str) -> bool:
    """Send the 6-digit signup verification code."""
    return send_sms(to_phone, f"Your ENTR verification code is {code}. It expires in 10 minutes.")
