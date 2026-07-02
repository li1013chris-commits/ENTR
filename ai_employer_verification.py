"""
AI-powered employer business verification.

Pipeline:
  1. Claude Vision extracts business name + address from the uploaded document.
  2. Fuzzy Jaccard matching compares extracted values against employer-entered values.
  3. >= 75% confidence -> verified. Below -> queued for manual review.
"""

import os
import re
import base64
import json
import logging
import anthropic

log = logging.getLogger(__name__)


# ── Image helpers ─────────────────────────────────────────────────────────────

def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def _media_type(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower()
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


# ── Document analysis via Claude Vision ───────────────────────────────────────

def analyze_business_document(image_path: str) -> dict:
    """
    Extract business_name, address, document_type from a business license/permit/utility bill.
    Returns dict with those keys; unreadable fields are None.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        return {
            "business_name": None, "address": None, "document_type": None,
            "_error": "ANTHROPIC_API_KEY is not configured.",
        }

    client = anthropic.Anthropic(api_key=api_key)
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": _media_type(image_path),
                            "data": _encode_image(image_path),
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "This is a business document (license, permit, or utility bill). "
                            "Extract the following in JSON format: "
                            "business_name, address, document_type. "
                            "If any field is unreadable, return null for that field. "
                            "Return only valid JSON, nothing else."
                        ),
                    },
                ],
            }],
        )
        return _parse_json(msg.content[0].text)
    except Exception as e:
        log.error("analyze_business_document failed: %s: %s", type(e).__name__, e)
        return {"business_name": None, "address": None, "document_type": None, "_error": str(e)}


# ── Fuzzy matching ─────────────────────────────────────────────────────────────

_ABBREVS = {
    "st": "street", "ave": "avenue", "blvd": "boulevard", "dr": "drive",
    "rd": "road", "ln": "lane", "ste": "suite", "apt": "apartment",
    "n": "north", "s": "south", "e": "east", "w": "west",
    "inc": "incorporated", "corp": "corporation", "co": "company", "llc": "llc",
}


def _word_set(text: str) -> set:
    if not text:
        return set()
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    words = [w for w in text.split() if w]
    return {_ABBREVS.get(w, w) for w in words}


def _jaccard(a: str, b: str) -> float:
    sa, sb = _word_set(a), _word_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def calculate_match_confidence(
    entered_name: str,
    entered_address: str,
    extracted_name: str | None,
    extracted_address: str | None,
) -> float:
    """Returns 0-100. Name weighted 60%, address 40%."""
    name_sim = _jaccard(entered_name or "", extracted_name or "")
    addr_sim = _jaccard(entered_address or "", extracted_address or "")
    return round((name_sim * 0.6 + addr_sim * 0.4) * 100, 1)


# ── Orchestration ──────────────────────────────────────────────────────────────

def run_employer_verification(
    employer_id: int,
    document_path: str,
    entered_name: str,
    entered_address: str,
    db,
) -> dict:
    """
    Full pipeline: extract -> match -> write result.
    Returns a dict with the final field values.
    """
    log.info("run_employer_verification: employer_id=%s", employer_id)

    result = {
        "extracted_business_name": None,
        "extracted_address": None,
        "document_type": None,
        "match_confidence": None,
        "business_verified": False,
        "business_verification_status": "pending",
        "failure_reason": None,
    }

    doc = analyze_business_document(document_path)
    if "_error" in doc:
        result["failure_reason"] = doc["_error"]
        _write(employer_id, result, db, timestamp=False)
        return result

    result["extracted_business_name"] = doc.get("business_name")
    result["extracted_address"]        = doc.get("address")
    result["document_type"]            = doc.get("document_type")

    confidence = calculate_match_confidence(
        entered_name, entered_address,
        result["extracted_business_name"], result["extracted_address"],
    )
    result["match_confidence"] = confidence
    log.info("run_employer_verification: confidence=%.1f%% for employer_id=%s", confidence, employer_id)

    if confidence >= 75:
        result["business_verified"]            = True
        result["business_verification_status"] = "verified"
    else:
        result["business_verification_status"] = "pending"
        result["failure_reason"] = (
            f"Document match confidence {confidence:.0f}% is below the 75% threshold. "
            "Your verification has been queued for manual review."
        )

    _write(employer_id, result, db, timestamp=result["business_verified"])
    return result


def _write(employer_id: int, r: dict, db, timestamp: bool) -> None:
    db.execute(
        """UPDATE employer_verifications SET
               extracted_business_name=?, extracted_address=?, document_type=?,
               match_confidence=?, business_verified=?,
               business_verification_status=?, failure_reason=?,
               verified_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE verified_at END
           WHERE employer_id=?""",
        (
            r["extracted_business_name"], r["extracted_address"], r["document_type"],
            r["match_confidence"], int(r["business_verified"]),
            r["business_verification_status"], r["failure_reason"],
            int(timestamp), employer_id,
        ),
    )
    db.commit()
