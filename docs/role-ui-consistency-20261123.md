# Role UI consistency — 2026-11-23

Approved scope: student/professor UI consistency review findings, mobile name clipping, warm lecture theme, implementation and deployment.

- Timetable, reservation list and notification management use the same reservation editor. Outcomes support booked/expired/completed/no_show according to existing server rules. Changing a student or dismissing a dirty editor asks before discarding notes. Saving a note keeps the editor available.
- Reservation status and period are independent. Default is all dates; optional today-onward and recent 90 days include an explicit Korean-time label.
- Browser and installed-app staff home both open the timetable. Consultation records/statistics have a distinct label. Student navigation order is explicit; suggestions always open the same landing page.
- Student cards show full time ranges, prioritize rescheduling before cancellation, and offer booking from the empty state.
- Mobile consultations up to 30 minutes reserve a line for names; under 20 minutes prioritize names only. Full time remains in accessible labels and details. Lectures use warm taupe, separate from reserved green and available cream.
- Delegated booking refreshes the timetable after success.

Validation: 404 local Python checks passed, 39 PostgreSQL-dependent cases skipped locally; lint, JavaScript syntax and 29 calendar assertions passed. Local browser startup is blocked by socket restrictions; PR #78 CI executes PostgreSQL and actual Chromium cases, including shared-editor note protection and outcome correction at 390px and 1280px.

Deployment: existing classbridge-staging Render service, staging branch. No database migration, permission change, paid resource or operational data edit. Deploy only after CI passes, then verify live revision, /healthz and served UI assets. Rollback uses the prior deployed revision c8e70e4d689fbba6ac34321ab61e49703400972b; no data rollback required.
