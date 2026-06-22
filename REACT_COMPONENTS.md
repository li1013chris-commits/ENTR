# Interview Scheduling React Components

This guide describes the React components needed for the interview scheduling feature. These components should be added to your React frontend (e.g., VeriHire project).

## Component Architecture

The interview scheduling feature requires components for both worker and employer flows.

---

## Worker Components

### 1. AvailabilityForm

**Location:** `src/components/interviews/AvailabilityForm.tsx`

**Purpose:** Allow workers to set their availability after submitting an application.

**Props:**
```typescript
interface AvailabilityFormProps {
  applicationId: number;
  onSubmit?: () => void;
  onCancel?: () => void;
}
```

**Features:**
- Two-column grid layout for days (Monday-Sunday)
- One-column list for times (Morning, Afternoon, Evening)
- Checkboxes for selection
- Submit button (saves to API: `PUT /api/worker/applications/{app_id}/availability`)
- Cancel button
- i18n translation support (use i18n keys like `availability.title`, `availability.monday`, etc.)
- Navy and gold styling consistent with design system

**Example Usage:**
```tsx
<AvailabilityForm 
  applicationId={123}
  onSubmit={() => navigate('/dashboard')}
  onCancel={() => navigate('/jobs')}
/>
```

**API Call:**
```typescript
const saveAvailability = async (applicationId: number, days: string[], times: string[]) => {
  const response = await fetch(`/api/worker/applications/${applicationId}/availability`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ days, times })
  });
  return response.json();
};
```

### 2. InterviewsList

**Location:** `src/components/interviews/InterviewsList.tsx`

**Purpose:** Display worker's scheduled interviews on the dashboard.

**Props:**
```typescript
interface InterviewsListProps {
  showEmpty?: boolean;
}
```

**Features:**
- Fetches from `GET /api/worker/interviews`
- Shows: job title, restaurant name, date/time, position
- "Add to Google Calendar" button (links to `google_event_id` or iCal format)
- Status indicator (scheduled, completed, cancelled)
- Responsive grid layout
- Empty state if no interviews

**Example Interview Card:**
```
┌─────────────────────────────────┐
│ Assistant Manager               │
│ Mario's Italian Kitchen         │
│                                 │
│ Wednesday, June 20 at 2:00 PM  │
│                                 │
│ [Add to Google Calendar] [More] │
└─────────────────────────────────┘
```

---

## Employer Components

### 3. ApplicationsListWithScheduling

**Location:** `src/components/interviews/ApplicationsListWithScheduling.tsx`

**Purpose:** Extend the existing applications list to include interview scheduling.

**Props:**
```typescript
interface ApplicationsListProps {
  jobId: number;
  applications: Application[];
  onSchedule?: (applicationId: number) => void;
}
```

**Features:**
- Renders existing application cards
- Adds "Schedule Interview" button to each applicant
- Button disabled if already scheduled
- Opens ScheduleInterviewModal when clicked

### 4. ScheduleInterviewModal

**Location:** `src/components/interviews/ScheduleInterviewModal.tsx`

**Purpose:** Allow employers to pick an interview time based on worker's availability.

**Props:**
```typescript
interface ScheduleInterviewModalProps {
  applicationId: number;
  workerName: string;
  workerAvailability?: {
    days: string[];
    times: string[];
  };
  onSuccess?: () => void;
  onClose?: () => void;
}
```

**Features:**
- Shows worker's availability in plain English
  - Example: "Available Monday, Wednesday, Friday afternoons and evenings"
- Date picker (restrict to available days only)
- Time picker (show available times for selected day)
- If no availability provided, show all time slots
- Confirmation button
- Loading state during API call
- Success/error messages

**Data Flow:**
1. Fetch worker availability: `GET /api/worker/applications/{app_id}/availability`
2. Format availability text
3. Filter date picker to available days
4. Show times for selected day
5. Submit: `POST /api/employer/applications/{app_id}/schedule-interview`

**Example Availability Display:**
```
Worker Availability:
"Available Monday, Wednesday, Friday 
 between 8am-12pm and 12pm-5pm"

Pick a time:
Date: [June 20 ▼]  (only Mon/Wed/Fri shown)
Time: [10:00 AM ▼] (morning slots shown)

[Schedule Interview]
```

**API Call:**
```typescript
const scheduleInterview = async (applicationId: number, dateTime: string) => {
  const response = await fetch(
    `/api/employer/applications/${applicationId}/schedule-interview`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scheduled_at: dateTime })
    }
  );
  return response.json();
};
```

### 5. ScheduledInterviewsList

**Location:** `src/components/interviews/ScheduledInterviewsList.tsx`

**Purpose:** Show all scheduled interviews for an employer.

**Props:**
```typescript
interface ScheduledInterviewsListProps {
  showEmpty?: boolean;
  onCancel?: (interviewId: number) => void;
}
```

**Features:**
- Fetches from `GET /api/employer/interviews`
- Shows: worker name, job title, date/time
- Sorted by date (earliest first)
- "View Details" link
- Cancel/Reschedule buttons
- Empty state message

**Example Interview Card:**
```
┌────────────────────────────────────┐
│ John Chen              Wednesday   │
│ Line Cook              Jun 20      │
│ 2:00 PM                            │
│                                    │
│ [View Details] [Reschedule]        │
└────────────────────────────────────┘
```

### 6. InterviewConfirmation

**Location:** `src/components/interviews/InterviewConfirmation.tsx`

**Purpose:** Show confirmation after interview is scheduled.

**Props:**
```typescript
interface InterviewConfirmationProps {
  interview: Interview;
  workerName: string;
  jobTitle: string;
  restaurantName: string;
}
```

**Features:**
- Shows scheduled date, time, location
- "Add to Google Calendar" button
- Reminder message about confirmation email being sent
- Close/Back button
- Celebration tone (you're all set, employer will reach out, etc.)

---

## Data Models

### Availability Object
```typescript
interface Availability {
  days: string[]; // ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
  times: string[]; // ['morning', 'afternoon', 'evening']
}

// Day mapping
const DAYS = {
  'monday': 'Monday',
  'tuesday': 'Tuesday',
  'wednesday': 'Wednesday',
  'thursday': 'Thursday',
  'friday': 'Friday',
  'saturday': 'Saturday',
  'sunday': 'Sunday',
};

// Time mapping
const TIMES = {
  'morning': '8am - 12pm',
  'afternoon': '12pm - 5pm',
  'evening': '5pm - 9pm',
};
```

### Interview Object
```typescript
interface Interview {
  id: number;
  application_id: number;
  employer_id: number;
  worker_id: number;
  scheduled_at: string; // ISO 8601 datetime
  google_event_id: string | null;
  status: 'scheduled' | 'completed' | 'cancelled';
  calendar_invite_sent: boolean;
  confirmation_email_sent: boolean;
  created_at: string;
  updated_at: string;
}
```

---

## Utility Functions

### formatAvailabilityText

Converts availability object to human-readable text.

```typescript
function formatAvailabilityText(availability: Availability): string {
  if (!availability || !availability.days || !availability.times) {
    return 'No availability provided';
  }

  const days = availability.days.map(d => DAYS[d]).join(', ');
  const times = availability.times.map(t => TIMES[t]).join(', ');
  
  return `Available ${days} ${times}`;
}

// Example output:
// "Available Monday, Wednesday, Friday mornings and afternoons"
```

### getDaysInRange

Get all available dates within a date range for scheduling.

```typescript
function getDaysInRange(
  startDate: Date,
  endDate: Date,
  availableDays: string[]
): Date[] {
  const available = [];
  const current = new Date(startDate);
  const dayNames = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
  
  while (current <= endDate) {
    const dayName = dayNames[current.getDay()];
    if (availableDays.includes(dayName)) {
      available.push(new Date(current));
    }
    current.setDate(current.getDate() + 1);
  }
  return available;
}
```

### getTimeSlots

Get available time slots for a specific day.

```typescript
function getTimeSlots(availableTimes: string[]): string[] {
  const timeMap = {
    'morning': ['08:00', '09:00', '10:00', '11:00'],
    'afternoon': ['12:00', '13:00', '14:00', '15:00', '16:00'],
    'evening': ['17:00', '18:00', '19:00'],
  };
  
  const slots: string[] = [];
  for (const time of availableTimes) {
    slots.push(...(timeMap[time] || []));
  }
  return slots;
}
```

---

## Styling Guidelines

All components should follow the existing design system:

**Colors:**
- Background: `#FFFFFF`
- Primary text: `#0A0F1E` (navy)
- Secondary text: `#6B7280` (gray)
- Accent: `#D4A853` (gold)
- Border: `#E5E7EB` (light gray)

**Typography:**
- Font: Inter
- Weights: 300, 400, 600, 700
- Card titles: 600 weight, 16-18px
- Body text: 400 weight, 14px
- Small labels: 400 weight, 12-13px

**Spacing:**
- Grid gap: 16px
- Card padding: 20-24px
- Margin between sections: 24-32px

**Border radius:**
- Buttons: 6px
- Cards: 10px
- Modal: 14px

**Example Button:**
```tsx
<button style={{
  padding: '12px 24px',
  borderRadius: '6px',
  backgroundColor: '#D4A853', // gold
  color: '#FFFFFF',
  fontWeight: 600,
  border: 'none',
  cursor: 'pointer',
}}>
  Schedule Interview
</button>
```

---

## Integration Points

### With Worker Dashboard
- Add `<InterviewsList />` to the main dashboard
- Show count of scheduled interviews in header
- Add action buttons to navigate to applications

### With Employer Applications View
- Replace or enhance application cards to include "Schedule Interview" button
- Add modal trigger for `<ScheduleInterviewModal />`
- Show scheduled interview status next to each applicant

### With Global Navigation
- Add "My Interviews" link to worker nav (if interviews exist)
- Add "Scheduled Interviews" section to employer dashboard

---

## i18n Keys

Add these to your translation files:

```javascript
{
  "availability.title": "When are you available?",
  "availability.subtitle": "Let employers know when you can do a quick call.",
  "availability.days": "Select Days",
  "availability.times": "Select Times",
  "availability.morning": "Morning (8am - 12pm)",
  "availability.afternoon": "Afternoon (12pm - 5pm)",
  "availability.evening": "Evening (5pm - 9pm)",
  "availability.submit": "Save Availability",
  "availability.note": "You can update this later. Employers will use this to schedule interviews.",
  
  "interview.schedule": "Schedule Interview",
  "interview.scheduled": "Interview Scheduled",
  "interview.time": "Interview Time",
  "interview.with": "Interview with",
  "interview.confirm": "Confirm Time",
  "interview.add_calendar": "Add to Google Calendar",
  "interview.details": "Interview Details",
  "interview.ready": "You are all set!",
  
  "status.interview_scheduled": "Interview Scheduled",
  "common.cancel": "Cancel",
}
```

---

## Testing Checklist

- [ ] AvailabilityForm saves and persists data correctly
- [ ] InterviewsList fetches and displays interviews
- [ ] ScheduleInterviewModal correctly filters dates/times
- [ ] Interview confirmation email sent in worker's language
- [ ] Google Calendar invite creates event and sends email
- [ ] Components responsive on mobile (under 600px width)
- [ ] All text translates correctly
- [ ] Accessibility: keyboard navigation, ARIA labels, sufficient contrast
- [ ] Error handling: show messages if API fails
- [ ] Empty states render correctly
