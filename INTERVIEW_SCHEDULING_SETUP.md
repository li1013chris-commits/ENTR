# Interview Scheduling Feature Setup

This document explains how to set up and use the interview scheduling feature that connects employers and workers after applications are submitted.

## Feature Overview

The interview scheduling feature enables:
1. **Worker Availability**: Workers select their availability (days and times) after submitting an application
2. **Employer Scheduling**: Employers view worker availability and pick specific interview times
3. **Calendar Integration**: Automatic Google Calendar event creation and invites sent to both parties
4. **Confirmation**: Confirmation screens and emails to both parties in their preferred language

## Database Changes

### New Tables

**`interviews`**: Stores interview scheduling information
- `id` - Primary key
- `application_id` - Foreign key to applications (unique)
- `employer_id` - Foreign key to users (employer)
- `worker_id` - Foreign key to users (worker)
- `scheduled_at` - Interview date/time
- `google_event_id` - ID of Google Calendar event
- `status` - 'scheduled', 'completed', or 'cancelled'
- `calendar_invite_sent` - Whether calendar invite was sent
- `confirmation_email_sent` - Whether confirmation email was sent
- `created_at`, `updated_at` - Timestamps

### Modified Tables

**`applications`**: Added new fields
- `worker_availability` - JSON field storing worker's availability
  - Format: `{"days": ["monday", "wednesday", "friday"], "times": ["morning", "afternoon"]}`
- Updated `status` enum to include `'interview_scheduled'`

## Google Calendar API Setup

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click "Select a Project" > "New Project"
3. Name it "ENTR Interview Scheduling"
4. Click "Create"

### Step 2: Enable Google Calendar API

1. In the Cloud Console, go to "APIs & Services" > "Library"
2. Search for "Google Calendar API"
3. Click on it and press "Enable"

### Step 3: Create Service Account

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Fill in:
   - Service account name: "entr-scheduler"
   - Click "Create and Continue"
4. Grant the service account "Editor" role
5. Click "Continue" then "Done"

### Step 4: Create JSON Key

1. In Credentials, under "Service Accounts", click the "entr-scheduler" account
2. Go to the "Keys" tab
3. Click "Add Key" > "Create new key"
4. Choose "JSON"
5. Click "Create" - a JSON file will download

### Step 5: Share Calendar Access

1. Get the service account email from the downloaded JSON key (look for `"client_email"`)
2. In Google Calendar:
   - Go to Settings for the calendar you want to use for interviews
   - Click "Share with specific people"
   - Add the service account email with "Make changes to events" permission

### Step 6: Configure Environment Variable

```bash
# Convert the JSON file to a single-line string and set as environment variable
export GOOGLE_CALENDAR_CREDENTIALS='{"type":"service_account",...}'
```

**Or** create a `.env` file in `/Users/christopherli/conductor/workspaces/entr/pattaya/`:

```
GOOGLE_CALENDAR_CREDENTIALS={"type":"service_account","project_id":"entr-xxxxx","private_key_id":"xxxxx","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"entr-scheduler@entr-xxxxx.iam.gserviceaccount.com","client_id":"xxxxx","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"https://www.googleapis.com/robot/v1/metadata/x509/..."}
```

## API Endpoints

### Worker Availability

**Save availability after application**
```
PUT /api/worker/applications/{app_id}/availability
Content-Type: application/json

{
  "days": ["monday", "wednesday", "friday"],
  "times": ["morning", "afternoon"]
}

Response: 200 OK
{
  "application": { ... }
}
```

**Get saved availability**
```
GET /api/worker/applications/{app_id}/availability

Response: 200 OK
{
  "availability": {
    "days": ["monday", "wednesday", "friday"],
    "times": ["morning", "afternoon"]
  }
}
```

### Employer Scheduling

**Schedule an interview**
```
POST /api/employer/applications/{app_id}/schedule-interview
Content-Type: application/json

{
  "scheduled_at": "2026-06-20T14:00:00"
}

Response: 201 Created
{
  "interview": {
    "id": 1,
    "application_id": 1,
    "employer_id": 1,
    "worker_id": 2,
    "scheduled_at": "2026-06-20T14:00:00",
    "google_event_id": "xxxxx",
    "status": "scheduled",
    ...
  }
}
```

**List employer's scheduled interviews**
```
GET /api/employer/interviews

Response: 200 OK
{
  "interviews": [...]
}
```

### Worker Interviews

**List worker's scheduled interviews**
```
GET /api/worker/interviews

Response: 200 OK
{
  "interviews": [...]
}
```

**Get interview details**
```
GET /api/interviews/{interview_id}

Response: 200 OK
{
  "interview": { ... }
}
```

## Frontend Components Needed

### Worker Side

1. **Availability Form** (`/worker/applications/{app_id}/set-availability`)
   - Checkbox grid for days (Mon-Sun)
   - Checkbox grid for times (Morning 8am-12pm, Afternoon 12pm-5pm, Evening 5pm-9pm)
   - Translation support via `data-i18n` attributes
   - Submits to `PUT /api/worker/applications/{app_id}/availability`

2. **Scheduled Interviews Display**
   - Shows list of upcoming interviews on worker dashboard
   - Displays: Date, time, restaurant name, position
   - Link to add to Google Calendar
   - Status indicator

### Employer Side

1. **Schedule Interview Modal/Page**
   - Shows worker's stated availability in plain language
     - Example: "Available Monday, Wednesday, Friday afternoons and evenings"
   - Date picker showing only available days
   - Time slots filtered to available times
   - Confirmation button
   - Submits to `POST /api/employer/applications/{app_id}/schedule-interview`

2. **Scheduled Interviews List**
   - Shows all upcoming interviews for the employer
   - Displays: Worker name, job title, date/time
   - Option to cancel or reschedule

## Implementation Status

### Completed
- [x] Database schema (interviews table, applications modifications)
- [x] Flask backend endpoints for all operations
- [x] Google Calendar API integration module
- [x] HTML template for worker availability form
- [x] Translation strings (English, Spanish)
- [x] API endpoints for employers to list interviews
- [x] Application status update to "Interview Scheduled"

### Still Needed
- [ ] React components for interview scheduling UI
- [ ] Email notifications (confirmation emails in worker's language)
- [ ] Availability display and formatting helper function
- [ ] Date picker UI for employers (respecting worker's availability)
- [ ] Google Calendar link generation for "Add to Calendar" button
- [ ] Testing and debugging

## Testing

### Manual Testing Checklist

1. **Worker Flow**
   - [ ] Create account as worker
   - [ ] Apply for a job
   - [ ] Redirected to availability form
   - [ ] Fill out availability (select days and times)
   - [ ] Availability saved and visible in dashboard

2. **Employer Flow**
   - [ ] Create account as employer
   - [ ] Post a job
   - [ ] View applications
   - [ ] See "Schedule Interview" button
   - [ ] Click button, see worker's availability displayed
   - [ ] Select a time that matches worker's availability
   - [ ] Interview created, status updated

3. **Google Calendar**
   - [ ] Verify event appears in employer's calendar
   - [ ] Verify invite sent to worker's email
   - [ ] Verify event includes job title, restaurant name, worker name
   - [ ] Verify bilingual description

4. **Translations**
   - [ ] Change language to Spanish
   - [ ] Repeat availability form test
   - [ ] Verify all labels translated correctly

## Troubleshooting

### Google Calendar API Issues

**Error: "GOOGLE_CALENDAR_CREDENTIALS not set"**
- Ensure `GOOGLE_CALENDAR_CREDENTIALS` environment variable is properly set
- Check that JSON is valid (no line breaks except in private_key)

**Error: "Failed to authenticate"**
- Verify service account has correct permissions
- Check that calendar has been shared with service account email
- Ensure private key format is correct (keep `\n` in the JSON string)

**Events not appearing**
- Check service account email has write access to the calendar
- Verify timezone settings are correct

## Notes

- Worker availability is stored as JSON in the applications table
- Google Calendar service uses service account (not user authentication)
- All event invites are sent automatically when interview is scheduled
- Email notifications are sent in the worker's preferred language
- Interviews cannot be scheduled outside of worker's stated availability
- Application status automatically updates to "interview_scheduled"

## Future Enhancements

- Rescheduling interviews
- Cancellation with notification
- Calendar sync from worker's own Google Calendar
- Timezone handling for remote workers
- Video call integration (Google Meet, Zoom)
- Interview notes and feedback
- No-show tracking and statistics
