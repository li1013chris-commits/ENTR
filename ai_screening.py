import os
import json
import anthropic

client = None


def get_client():
    global client
    if client is None:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return client


def screen_application(job: dict, worker: dict, cover_letter: str,
                        verification_status: str | None = None) -> tuple[int, str]:
    """
    Score a job application 0-100 using structured skill comparison.
    Unverified workers are noted in the summary and their score is reduced by 10.
    Returns (score, summary).
    """
    verified_note = ""
    if verification_status == "verified":
        verified_note = "\nVerification Status: Identity verified by ENTR (+5 points)"
    elif verification_status == "flagged":
        verified_note = "\nVerification Status: Verification flagged — identity unconfirmed (-5 points)"
    else:
        verified_note = "\nVerification Status: Identity not yet verified (-10 points)"

    prompt = f"""You are a hiring assistant for immigrant-owned restaurants. Evaluate this job application using structured skill matching.

JOB DETAILS:
- Title: {job['title']}
- Pay: {job['pay']}
- Hours: {job['hours']}
- Experience Required: {job['experience_required']} years
- Language Preference: {job['language_preference'] or 'None specified'}
- Description: {job['description'] or 'None'}

APPLICANT PROFILE:
- Name: {worker['name']}
- Years of Experience: {worker['experience_years']} years
- Languages Spoken: {worker['languages_spoken'] or 'Not specified'}
- Dialect Preference: {worker.get('dialect_preference') or 'Not specified'}
- Availability: {worker.get('availability') or 'Not specified'}
- Core Skills: {worker.get('skills') or 'Not specified'}
- Bio: {worker['bio'] or 'Not provided'}
- Cover Letter: {cover_letter or 'Not provided'}
{verified_note}

EVALUATION CRITERIA:
1. Skills Match: Do the applicant's core skills align with the job requirements?
2. Experience Level: Does their experience meet or exceed the job requirement?
3. Language Fit: Does their language profile match the job's language preference?
4. Availability: Is their stated availability compatible with the job hours?
5. Motivation: Does the cover letter show genuine interest and understanding of the role?

Respond with ONLY a JSON object with this exact structure:
{{
  "skills_match": <0-100>,
  "experience_match": <0-100>,
  "language_match": <0-100>,
  "availability_match": <0-100>,
  "motivation_match": <0-100>,
  "score": <integer 0-100>,
  "summary": "<2-3 sentence explanation>"
}}

The overall score should weight these factors appropriately. Consider the applicant's structured skills when available."""

    try:
        message = get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text   = message.content[0].text.strip()
        result = json.loads(text)
        score  = max(0, min(100, int(result.get("score", 50))))
        summary = result.get("summary", "Unable to generate summary.")

        # Apply verification penalty/bonus (already factored into the prompt guidance)
        if verification_status == "verified":
            score = min(100, score + 5)
        elif verification_status == "flagged":
            score = max(0, score - 5)
        else:
            score = max(0, score - 10)

        return score, summary
    except Exception as e:
        return 50, f"AI screening unavailable: {e}"
