# ENTR - Build Progress

## Restart the server

```bash
cd /Users/christopherli/conductor/workspaces/entr/pattaya
source venv/bin/activate
python app.py
# Runs on http://localhost:5000
```

If port 5000 is already in use:

```bash
pkill -f "python app.py"
python app.py
```

---

## What has been built

### Backend (Python / Flask)

**`app.py`** - 22 routes, all working and tested end-to-end:

| Route | Purpose |
|---|---|
| `GET /` | Landing page (redirects authenticated users to their dashboard) |
| `GET/POST /signup` | Registration - workers are redirected to `/worker/verify` after signup |
| `GET/POST /login` | Authentication with password hashing |
| `GET /logout` | Session clear |
| `GET /set-language/<lang>` | Switches UI language and persists to user record |
| `GET /employer/dashboard` | Lists employer's jobs with applicant counts |
| `GET/POST /employer/post-job` | Job posting form |
| `POST /employer/jobs/<id>/toggle` | Open/close a job listing |
| `GET /employer/jobs/<id>/applications` | AI-ranked applicant list with verification badges |
| `POST /employer/applications/<id>/status` | Update applicant status (pending/reviewed/accepted/rejected) |
| `GET /employer/applications/<id>/verification` | Employer-facing verification report (no raw ID shown) |
| `GET /worker/dashboard` | Worker's application history with AI scores |
| `GET/POST /worker/profile` | Edit bio, experience, languages, phone |
| `GET /worker/jobs` | Browse all open jobs |
| `GET/POST /worker/jobs/<id>/apply` | Apply with optional cover letter; AI screens immediately |
| `GET /worker/verify` | Two-step verification page (step-aware UI) |
| `POST /worker/verify/upload-id` | Accepts JPG/PNG of government ID |
| `POST /worker/verify/upload-selfie` | Accepts selfie, triggers full verification pipeline |
| `POST /worker/verify/resubmit` | Resets verification so worker can start over |
| `GET /verification/image/<id>/<type>` | Serves ID/selfie only to the owning worker (403 otherwise) |

**`database.py`** - SQLite with safe migration:
- `init_db()` creates all four tables if they don't exist
- `_migrate()` handles the verifications table schema upgrade (old `user_id` column renamed to `worker_id`, 10 new columns added) without data loss
- `detect_types=sqlite3.PARSE_DECLTYPES` returns native Python types; templates use `(value | string)[:10]` for date display

**`ai_screening.py`** - Application scoring:
- Calls `claude-sonnet-4-6` with job details + worker profile + cover letter
- Returns a score (0-100) and a 2-3 sentence summary
- Verified workers score as-is; unverified workers receive a -10 point penalty and a note in their summary
- Graceful fallback: returns `(50, error message)` if the API is unavailable

**`ai_verification.py`** - Identity verification pipeline:
- Step 1: `analyze_id_document()` - Claude Vision extracts `full_name`, `date_of_birth`, `document_type`, `expiration_date` from an ID image via structured JSON prompt
- Step 2: `compare_faces_aws()` - AWS Rekognition `CompareFaces` API. Returns `(None, False)` immediately if `AWS_ACCESS_KEY_ID` is not set in the environment (no boto3 call, no crash)
- Step 2 fallback: `compare_faces_claude()` - Two-image Claude Vision prompt estimates similarity 0-100
- `run_verification()` orchestrates the pipeline and writes results to the database. If both face services fail, sets status to `pending` for manual review rather than blocking the worker
- `calculate_age()` derives age from ISO date string; sets `age_verified = False` if under 18

### Database schema

**`users`**: id, email, password_hash, role, name, phone, language_pref, bio, experience_years, languages_spoken, restaurant_name, created_at

**`jobs`**: id, employer_id, title, description, pay, hours, experience_required, language_preference, location, status, created_at

**`applications`**: id, job_id, worker_id, cover_letter, ai_score, ai_summary, status, created_at

**`verifications`**: id, worker_id, id_document_path, selfie_path, extracted_dob, extracted_name, face_match_score, age_verified, identity_verified, verification_status, verified_at, failure_reason, created_at

### Frontend

**Templates** (13 HTML files):
- `base.html` - Sticky nav, language selector, frosted-glass scroll effect, multi-column footer with LinkedIn/Contact/Help/Ask AI/About links
- `index.html` - Full landing page (see Design section below)
- `login.html` - Minimal centered form
- `signup.html` - Role tab toggle (Restaurant Owner / Job Seeker) with dynamic field sets per role; no emojis, SVG icons
- `employer/dashboard.html` - Job listing cards with applicant counts
- `employer/post_job.html` - Job posting form
- `employer/applications.html` - Ranked applicant cards with verification badge, face match score, age confirmation, and "View Report" link per applicant
- `employer/verification_detail.html` - Extracted name, DOB, age confirmation, face match percentage bar, privacy note (no raw ID shown)
- `worker/dashboard.html` - Application status cards with AI scores
- `worker/browse_jobs.html` - 3-column job grid with pay/hours/location pills
- `worker/apply.html` - Cover letter form
- `worker/profile.html` - Profile edit form
- `worker/verify.html` - Step-indicator verification flow with drag-and-drop upload zones, status banners, privacy notice, and resubmit capability

**`static/css/style.css`** - Full custom design system:
- Color palette: `#FFFFFF` background, `#0A0F1E` navy, `#D4A853` gold accent, `#6B7280` secondary text
- Typography: Inter (300/400/600/700 weights)
- All dark backgrounds removed except the footer
- Border-radius: 6px buttons, 10px cards, 14px modals
- Three-layer box shadows for floating UI cards

**`static/js/main.js`** - Vanilla JS with:
- Full i18n system with translations for 6 languages (EN, ES, ZH, FR, PT, VI)
- `initRoleTabs()` - signup page tab switching with dynamic field visibility
- `initFeatureTabs()` - Why ENTR numbered tab navigation (01/02/03) with panel switching
- `initStickyNav()` - frosted-glass nav on scroll via `backdrop-filter: blur(18px)`
- `initScrollAnimations()` - IntersectionObserver fade-in with directional variants (left/right/scale) and stagger delays
- `initScores()` - colors AI score circles (green/yellow/red)

### Landing page sections

1. **Hero** - Centered headline (`clamp(52px, 7vw, 80px)`, `font-weight: 700`) above a full-width browser mockup showing the employer dashboard (sidebar job list + AI-ranked applications). The browser has `perspective(1800px) rotateX(5deg)` tilt that eases to `rotateX(1deg)` on hover. Dot-grid texture via CSS radial-gradient. Entrance animations stagger badge, heading, subtitle, buttons, and browser with cubic-bezier spring easing.

2. **Why ENTR** - Two-column tabbed layout (300px nav + 1fr panel). Left: numbered tabs (01/02/03) with gold left-border accent when active and `max-height` transition revealing the description. Right: deep navy panel with dual radial gold glows. Three floating card states:
   - 01 AI Screening: ranked applicant list with score circles, fill bars, and Verified/Pending badges
   - 02 Multilingual: 6-language selector grid + Spanish speech bubble + tilted English translation card
   - 03 Fast and Simple: prefilled job form with blinking cursor + pulsing "Posted in 47 seconds" badge

3. **How It Works** - Three alternating rows with activity-feed style navy panels instead of browser mockups:
   - Step 01: "New job posted" notification + stacked "7 workers nearby" card
   - Step 02: Applicant avatar + chips (experience, language, ID Verified) + "+4 more" card
   - Step 03: AI-ranked applicant score row + "Claude AI reviewed 5 applications in 3 seconds" card

4. **CTA band** - Centered headline on white with subtle gold gradient, two buttons

5. **Footer** - Dark navy, two-column link grid (Platform / Company), tagline

---

## What still needs to be done

### Recently completed ✅

- [x] **Worker profile schema expansion** - Added `skills`, `availability`, `dialect_preference` columns to users table. Safe migration for existing databases.
- [x] **Worker profile API endpoints** - Both GET and PUT `/api/worker/profile` now handle all new fields.
- [x] **Structured skill-based AI screening** - Updated `screen_application()` to evaluate skills, experience, language, availability, and motivation independently with detailed breakdown.
- [x] **Session validation endpoint** - Added `POST /api/auth/validate-session` for frontend to validate localStorage-based sessions on page load.

### High priority

- [ ] **Email notifications** - Send email when a worker applies, when verification completes, and when an employer updates application status. Flask-Mail or Resend API.
- [ ] **Admin panel** - Route for manual verification review when the pipeline returns `pending`. Currently there is no way to mark a queued verification as verified/failed without direct DB access.
- [ ] **Employer plan/tier** - The code references a pricing gate (free tier sees badge only, paid tier sees full verification report) but there is no `is_pro` column on users and no payment integration. Currently all employers see the full report.
- [ ] **Search and filter on browse jobs** - Workers currently see all open jobs with no way to filter by pay, hours, location, or language.

### Medium priority

- [ ] **Job application status emails** - Workers have no way to know their application was reviewed/accepted/rejected unless they log in.
- [ ] **Resume/CV upload** - Workers can only enter a bio text field. A PDF upload would improve AI screening quality significantly.
- [ ] **Stripe integration** - Implement the actual employer pricing gate (free/pro plans) with Stripe Checkout or Billing.
- [ ] **Password reset** - No forgot-password flow exists. Users who lose their password cannot recover their account.
- [ ] **Job expiry** - Jobs stay open indefinitely unless the employer manually closes them. Auto-close after 30 days would reduce stale listings.
- [ ] **Worker profile photo** - Verification captures a selfie but it is never displayed on the profile or application card.

### Lower priority / nice to have

- [ ] **Employer analytics** - Views, applicant funnel, time-to-hire metrics per job.
- [ ] **Application messaging** - In-platform chat or notes between employer and applicant.
- [ ] **Saved/bookmarked jobs** - Workers cannot save jobs to apply to later.
- [ ] **PostgreSQL migration** - The app uses SQLite. `database.py` is isolated enough that swapping to `psycopg2` and updating the connection string is straightforward, but not done.
- [ ] **Production deployment** - No Dockerfile, no `gunicorn` config, no CI/CD pipeline, no HTTPS setup. Currently development-only.
- [ ] **Test suite** - No automated tests. The verification and screening flows were tested manually end-to-end.
- [ ] **Rate limiting** - No protection against brute-force login attempts or bulk application submission.
- [ ] **Session security** - `SECRET_KEY` defaults to a hardcoded dev string if the env var is missing.

---

## Key design decisions

### Architecture

**Flask over Django or FastAPI** - The app is small and SQLite-backed. Flask's lack of an ORM was intentional: raw SQL gives full control over the join queries needed to pull verification status alongside applications in a single query.

**SQLite in development** - Zero-config, file-based, ships with Python. The `database.py` module is isolated so swapping to PostgreSQL means changing the connection string and replacing `sqlite3` with `psycopg2` - no other files need to change.

**No frontend framework** - Vanilla JS + CSS. The i18n system, tab logic, and scroll animations are all under 200 lines each. Adding React would have tripled the setup complexity for no meaningful benefit at this scale.

**Sessions over JWT** - Server-side sessions are simpler and safer for a monolithic Flask app. JWT would only make sense if there were a separate API consumed by a mobile app.

### Verification pipeline

**Claude Vision first, Rekognition second** - The design decision was to use Claude for ID text extraction (Rekognition does not do OCR on ID documents) and Rekognition for face comparison (purpose-built, more accurate). Claude Vision is the fallback for face comparison when AWS is not configured. This means the app is fully functional without any AWS setup.

**Never block workers** - If the verification pipeline fails for any reason (API error, timeout, bad image), the status is set to `pending` and the worker is allowed to apply. Blocking workers due to infrastructure failures would be a worse user experience than allowing unverified applications through.

**Images outside `static/`** - Verification images are saved to `uploads/verification/` which is not served by Flask's static file handler. A dedicated authenticated route checks ownership before serving any image.

**Age verification logged but not enforced at application** - The `age_verified` boolean is stored and shown to employers, but workers under 18 are not blocked from applying. This is a deliberate choice because age requirements vary by job type and jurisdiction; the employer sees the flag and decides.

### Frontend

**Gold (`#D4A853`) instead of orange** - The original accent was `#F97316` (vibrant orange) which visually resembled Anthropic's brand colors. Gold is warmer, more premium, and distinct from both Claude orange and generic amber.

**Perspective tilt on hero mockup** - `perspective(1800px) rotateX(5deg)` on the browser mockup is the same technique used by Linear, Vercel, and Stripe to make product screenshots feel like they are floating toward the viewer. It eases on hover to `rotateX(1deg)` to reward interaction.

**Tab navigation for Why ENTR** - Flat feature lists feel like bullet points. The numbered tab pattern (borrowed from ENTR Technologies' own site style) forces one feature to be active at a time, makes each panel feel like a reveal, and gives the mockup cards room to breathe at full panel width.

**Activity feed cards for How It Works** - Browser-chrome mockups in the step rows looked like screenshots from a help article. Activity-feed style notification cards floating over a navy panel look like product moments: real data, real state, real UI.

**Inter at 300/400/600/700** - Garamond (the prior font) is elegant but inappropriate for a data-dense hiring platform where small labels, score numbers, and status badges need to be legible at 9-11px. Inter is designed for screen legibility at small sizes.
