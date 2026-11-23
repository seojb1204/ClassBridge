# Calendar clarity update

- Lectures use a warm taupe surface and a brown leading border, distinct from green booked consultations and cream available consultations.
- Visible lecture labels contain the title only. Accessible labels retain the event type, and detail actions retain the original event and complete title/time.
- Staff timetable, staff booking calendar, and student calendar share one legend renderer with role-appropriate labels.
- Mobile weekly cards use larger text and a two-line title clamp; the existing time-axis geometry and consultation-first overlap policy remain unchanged.
- No API, authorization, database schema, or booking policy changes.

Validation: 22 focused Python tests passed, JavaScript slot-label/weekday/overlap/cache regressions passed, changed Python tests pass Ruff. Local browser tests are blocked by this runtime's Chromium socket restriction; the PR CI runs the browser checks including 360px, 390px, desktop and list layouts. Merge/deployment requires reviewing CI results.

Rollback: revert this UI-only commit and deploy the previous revision; no data migration or restoration is needed.

Mobile follow-up: consultations of 30 minutes or less show the start time on one line and attendee label on the next. Full time ranges remain in accessible labels and details; desktop/list time ranges are unchanged. The 20-minute regression checks that the name fits inside the card.

Follow-up validation: 29 JavaScript label/calendar assertions passed and git diff --check passed. Browser regression cases were attempted with bundled and system Chromium but could not start in this environment; mobile visual validation and deployment remain pending.
