"""
AI-powered worker identity verification.

Pipeline:
  1. Claude Vision reads the ID document and extracts name / DOB.
  2. AWS Rekognition compares the ID photo face against the selfie.
     If Rekognition is unavailable, Claude Vision is used as a fallback.
  3. Results are written back to the verifications table.
"""

import os
import base64
import json
import logging
import anthropic
from datetime import date

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _anthropic_client():
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def _media_type(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower()
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")


def _parse_json_response(text: str) -> dict:
    """Strip markdown fences then parse JSON."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def calculate_age(dob_str: str | None) -> int | None:
    if not dob_str:
        return None
    try:
        dob = date.fromisoformat(dob_str)
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return None


# ── Step 1: ID document analysis ─────────────────────────────────────────────

def analyze_id_document(image_path: str) -> dict:
    """
    Call Claude Vision on a government ID image.
    Returns dict with keys: full_name, date_of_birth, document_type, expiration_date.
    Any unreadable field is None.
    """
    client = _anthropic_client()
    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
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
                            "This is a government-issued ID document. "
                            "Extract the following information in JSON format: "
                            "full_name, date_of_birth (YYYY-MM-DD format), "
                            "document_type, expiration_date. "
                            "If any field is unreadable, return null for that field. "
                            "Return only valid JSON, nothing else."
                        ),
                    },
                ],
            }],
        )
        return _parse_json_response(message.content[0].text)
    except Exception as e:
        log.error("analyze_id_document failed: %s: %s", type(e).__name__, e)
        return {
            "full_name": None,
            "date_of_birth": None,
            "document_type": None,
            "expiration_date": None,
            "_error": str(e),
        }


# ── Step 2: Face comparison ───────────────────────────────────────────────────

def compare_faces_aws(id_image_path: str, selfie_path: str) -> tuple[float | None, bool]:
    """
    Compare faces with AWS Rekognition.
    Returns (similarity_score, success).
    success=False means Rekognition is unavailable — caller automatically falls back to Claude Vision.
    If AWS_ACCESS_KEY_ID is not set in the environment, skips Rekognition entirely.
    """
    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        return None, False  # No credentials configured — use Claude Vision fallback
    try:
        import boto3  # noqa: F401
        rek = boto3.client(
            "rekognition",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
        with open(id_image_path, "rb") as f:
            source_bytes = f.read()
        with open(selfie_path, "rb") as f:
            target_bytes = f.read()

        resp = rek.compare_faces(
            SourceImage={"Bytes": source_bytes},
            TargetImage={"Bytes": target_bytes},
            SimilarityThreshold=0,
        )
        matches = resp.get("FaceMatches", [])
        score = round(matches[0]["Similarity"], 1) if matches else 0.0
        return score, True
    except ImportError:
        log.warning("compare_faces_aws: boto3 not installed, falling back to Claude Vision")
        return None, False
    except Exception as e:
        log.warning("compare_faces_aws failed (%s: %s), falling back to Claude Vision", type(e).__name__, e)
        return None, False


def compare_faces_claude(id_image_path: str, selfie_path: str) -> tuple[float, bool]:
    """
    Fallback face comparison via Claude Vision.
    Returns (similarity_score 0-100, success).
    """
    client = _anthropic_client()
    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": _media_type(id_image_path),
                            "data": _encode_image(id_image_path),
                        },
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": _media_type(selfie_path),
                            "data": _encode_image(selfie_path),
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "The first image is the face on a government ID. "
                            "The second image is a selfie from the same person. "
                            "Compare the faces and estimate whether they are the same individual. "
                            "Return only JSON: "
                            '{"similarity_score": <integer 0-100>} '
                            "where 0 = definitely different, 100 = definitely the same person."
                        ),
                    },
                ],
            }],
        )
        result = _parse_json_response(message.content[0].text)
        return float(result.get("similarity_score", 50)), True
    except Exception as e:
        log.error("compare_faces_claude failed: %s: %s", type(e).__name__, e)
        return 50.0, False


# ── Orchestration ─────────────────────────────────────────────────────────────

def run_verification(worker_id: int, id_image_path: str, selfie_path: str, db) -> dict:
    """
    Full verification pipeline. Writes results to the verifications row for worker_id.
    Returns a dict with the final field values.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        msg = "ANTHROPIC_API_KEY is not set. Open pattaya/.env and replace the placeholder with your real key."
        log.error("run_verification: %s", msg)
        raise RuntimeError(msg)

    log.info("run_verification: starting for worker_id=%s", worker_id)
    result = {
        "extracted_name": None,
        "extracted_dob": None,
        "face_match_score": None,
        "age_verified": False,
        "identity_verified": False,
        "verification_status": "pending",
        "failure_reason": None,
    }

    # ── Step 1: ID analysis ───────────────────────────────────────────────────
    log.info("run_verification: step 1 — analyzing ID document at %s", id_image_path)
    id_info = analyze_id_document(id_image_path)
    if "_error" in id_info:
        log.warning("run_verification: ID analysis returned error: %s", id_info["_error"])
    result["extracted_name"] = id_info.get("full_name")
    result["extracted_dob"]  = id_info.get("date_of_birth")

    age = calculate_age(result["extracted_dob"])
    result["age_verified"] = (age is not None and age >= 18)

    # ── Step 2: Face matching ─────────────────────────────────────────────────
    log.info("run_verification: step 2 — comparing faces")
    score, ok = compare_faces_aws(id_image_path, selfie_path)
    if not ok:
        log.info("run_verification: AWS Rekognition unavailable, trying Claude Vision fallback")
        score, ok = compare_faces_claude(id_image_path, selfie_path)

    if not ok or score is None:
        log.error("run_verification: both face comparison methods failed for worker_id=%s", worker_id)
        result["failure_reason"] = (
            "Face comparison service unavailable. Your verification has been queued for manual review."
        )
        _write(worker_id, result, db, timestamp=False)
        _delete_biometric_files(worker_id, [id_image_path, selfie_path], db)
        return result

    log.info("run_verification: face match score=%.1f for worker_id=%s", score, worker_id)

    result["face_match_score"] = score

    if score >= 80:
        result["identity_verified"] = True
        result["verification_status"] = "verified"
    else:
        result["identity_verified"] = False
        result["verification_status"] = "flagged"
        result["failure_reason"] = (
            f"Face match score ({score:.0f}%) is below the required 80% threshold. "
            "Please resubmit with a clearer, well-lit selfie."
        )

    _write(worker_id, result, db, timestamp=result["verification_status"] == "verified")
    _delete_biometric_files(worker_id, [id_image_path, selfie_path], db)
    return result


def _delete_biometric_files(worker_id: int, paths: list, db) -> None:
    """
    Data retention policy: ID photos and selfies are deleted from the server
    immediately after the verification pipeline completes. The extracted data
    (name, DOB, match score) is kept; the raw biometric images are not.
    """
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError as e:
            log.warning("could not delete verification file %s: %s", p, e)
    db.execute(
        "UPDATE verifications SET id_document_path=NULL, selfie_path=NULL WHERE worker_id=?",
        (worker_id,),
    )
    db.commit()
    log.info("run_verification: biometric files deleted for worker_id=%s", worker_id)


def _write(worker_id: int, r: dict, db, timestamp: bool) -> None:
    db.execute(
        """UPDATE verifications SET
               extracted_name=?, extracted_dob=?, face_match_score=?,
               age_verified=?, identity_verified=?, verification_status=?,
               failure_reason=?,
               verified_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE verified_at END
           WHERE worker_id=?""",
        (
            r["extracted_name"], r["extracted_dob"], r["face_match_score"],
            int(r["age_verified"]), int(r["identity_verified"]),
            r["verification_status"], r["failure_reason"],
            int(timestamp), worker_id,
        ),
    )
    db.commit()
