# ENTR - AI-Powered Hiring for Immigrant-Owned Restaurants

ENTR connects immigrant-owned restaurants with qualified workers. Claude AI screens applications and verifies worker identities automatically.

## Features

- **Two user types**: Restaurant owners (employers) and job seekers (workers)
- **Employer dashboard**: Post listings, view AI-ranked applications with verification badges
- **Worker dashboard**: Browse jobs, apply, complete identity verification
- **AI screening**: Claude API scores each application 0-100 with a written summary
- **Identity verification**: Claude Vision reads government IDs; AWS Rekognition (or Claude fallback) matches faces
- **Interview scheduling**: Workers set availability; employers pick times; Google Calendar invites sent to both
- **Multilingual**: Full UI in English, Spanish, Chinese, French, Portuguese, and Vietnamese

## Tech Stack

- **Backend**: Python 3.11+ / Flask
- **Database**: SQLite via Python built-in `sqlite3`
- **Frontend**: HTML, CSS, JavaScript (no frameworks)
- **AI**: Anthropic Claude (`claude-sonnet-4-6`) for screening and ID analysis
- **Face matching**: AWS Rekognition (optional; falls back to Claude Vision automatically)

## Setup

### 1. Clone and enter the directory

```bash
cd pattaya
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your keys (see sections below for each service).

### 5. Run the app

```bash
python app.py
```

The app initializes the database on first run and starts on `http://localhost:5000`.

---

## Environment Variables

### Required

```
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=some-long-random-string
DATABASE_PATH=entr.db
```

Get your Anthropic API key at [console.anthropic.com](https://console.anthropic.com).

### Optional: AWS Rekognition (face matching)

```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

**If these are not set, ENTR automatically uses Claude Vision for face comparison instead. No configuration or code change is needed.** Rekognition is more accurate for production use; Claude Vision is a fully functional fallback for development and environments without AWS access.

#### How to get AWS credentials

1. Sign in to the [AWS Console](https://console.aws.amazon.com).

2. Go to **IAM** (Identity and Access Management).

3. In the left sidebar, click **Users**, then **Create user**.

4. Give the user a name (e.g. `entr-rekognition`) and click **Next**.

5. Select **Attach policies directly**, search for `AmazonRekognitionReadOnlyAccess`, and attach it.

6. Complete the user creation, then open the user and go to the **Security credentials** tab.

7. Click **Create access key**, choose **Application running outside AWS**, and download the CSV.

8. Copy `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from the CSV into your `.env` file.

9. Set `AWS_REGION` to the region you want to use (e.g. `us-east-1`). Rekognition is available in all major regions.

#### Rekognition vs. Claude Vision fallback

| | AWS Rekognition | Claude Vision fallback |
|---|---|---|
| Requires AWS account | Yes | No |
| Accuracy | High (purpose-built) | Good (general vision model) |
| Cost | ~$0.001 per comparison | Included in Claude API usage |
| Auto-selected when | `AWS_ACCESS_KEY_ID` is set | `AWS_ACCESS_KEY_ID` is not set |

---

## Identity Verification Flow

Workers complete a two-step verification before their applications are ranked:

1. **Upload government ID** (passport, driver's license, state ID) - Claude Vision extracts name and date of birth.
2. **Upload a selfie** - the face is compared against the ID photo.

Verification results:
- **Verified**: face match score >= 80%. Green badge on all applications.
- **Flagged**: face match score < 80%. Worker is prompted to resubmit.
- **Pending**: API unavailable. Queued for manual review. Worker can still apply.

Employers see verification status and match score on each application. Raw ID documents are never shown to employers.

---

## Database Schema

| Table | Key columns |
|---|---|
| `users` | id, email, password_hash, role, name, phone, language_pref, bio, experience_years, languages_spoken, restaurant_name, skills, availability, dialect_preference |
| `jobs` | id, employer_id, title, pay, hours, experience_required, language_preference, location, description, status |
| `applications` | id, job_id, worker_id, cover_letter, ai_score, ai_summary, worker_availability, status |
| `verifications` | id, worker_id, id_document_path, selfie_path, extracted_name, extracted_dob, face_match_score, age_verified, identity_verified, verification_status, verified_at, failure_reason |
| `interviews` | id, application_id, employer_id, worker_id, scheduled_at, google_event_id, status, calendar_invite_sent, confirmation_email_sent |

## Project Structure

```
pattaya/
├── app.py                  # Flask routes and app config
├── database.py             # SQLite init, connection helpers, migration
├── ai_screening.py         # Claude API - application scoring
├── ai_verification.py      # Claude Vision + Rekognition - ID verification
├── google_calendar.py       # Google Calendar API integration
├── email_service.py         # Email sending (SMTP)
├── requirements.txt
├── .env.example
├── README.md
├── PROGRESS.md
├── INTERVIEW_SCHEDULING_SETUP.md
├── uploads/
│   └── verification/       # ID and selfie uploads (not web-accessible)
├── static/
│   ├── css/style.css
│   └── js/main.js
└── templates/
    ├── base.html
    ├── index.html
    ├── login.html
    ├── signup.html
    ├── employer/
    │   ├── dashboard.html
    │   ├── post_job.html
    │   ├── applications.html
    │   └── verification_detail.html
    └── worker/
        ├── dashboard.html
        ├── browse_jobs.html
        ├── apply.html
        ├── profile.html
        ├── verify.html
        └── set_availability.html
```

## Email verification (SMTP configuration)

After a user signs up, ENTR sends a verification email with a one-time confirmation link.

If SMTP is not configured, the verification link is printed to the server console instead, so development works without a mail server.

Add the following variables to your `.env` file to enable real email delivery:

```
# Required for sending email
MAIL_SERVER=smtp.gmail.com        # your SMTP host
MAIL_PORT=587                     # 587 for TLS, 465 for SSL, 25 for plain
MAIL_USE_TLS=true                 # true for port 587
MAIL_USE_SSL=false                # true only for port 465
MAIL_USERNAME=you@example.com     # SMTP login username
MAIL_PASSWORD=your_app_password   # SMTP login password (use an App Password for Gmail)
MAIL_DEFAULT_SENDER=noreply@entr.app  # From address shown in emails

# URL of your frontend (used to build the verification link)
FRONTEND_URL=http://localhost:5173
```

**Gmail setup:** In Google Account settings, enable 2-Step Verification, then generate an App Password under Security and use that as `MAIL_PASSWORD`.

**SendGrid / Mailgun:** Set `MAIL_SERVER` to their SMTP relay host, `MAIL_PORT` to 587, and use your API key as the password.

The endpoint `POST /api/auth/resend-verification` (requires auth) re-sends the verification email if the user has not yet verified.

---

## Interview Scheduling (Google Calendar Integration)

ENTR can automatically create Google Calendar events and send invites when employers schedule interviews.

### Setup Google Calendar API

**Step 1: Create a Google Cloud Project**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click "Select a Project" > "New Project"
3. Name it "ENTR" and click "Create"

**Step 2: Enable Google Calendar API**
1. Go to "APIs & Services" > "Library"
2. Search for "Google Calendar API" and click "Enable"

**Step 3: Create Service Account**
1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Name: "entr-scheduler", click "Create and Continue"
4. Grant "Editor" role, click "Continue" then "Done"

**Step 4: Create JSON Key**
1. Under Service Accounts, click "entr-scheduler"
2. Go to "Keys" tab
3. Click "Add Key" > "Create new key" > "JSON" > "Create"
4. A JSON file will download

**Step 5: Get Service Account Email & Share Calendar**
1. Open the downloaded JSON file
2. Copy the `"client_email"` value
3. In your Google Calendar, go to Settings
4. Click "Share with specific people"
5. Add the service account email with "Make changes to events" permission

**Step 6: Set Environment Variable**
Add to `.env`:
```
GOOGLE_CALENDAR_CREDENTIALS={"type":"service_account","project_id":"entr-xxxxx",...}
```

Copy the entire contents of the downloaded JSON file as the value (it will be one long line).

For detailed setup instructions, see [INTERVIEW_SCHEDULING_SETUP.md](./INTERVIEW_SCHEDULING_SETUP.md).

---

## Security notes

- Verification images are stored in `uploads/verification/` which is outside `static/` and not web-accessible.
- Images are served only through an authenticated route that checks ownership.
- Employers never receive raw ID documents; only extracted fields and the match percentage are shared.
