# Mobile QR and booking UI release (2026-11-06)

- Site and published survey QR images download as PNG; SVG routes remain compatible.
- Explicit mobile date selection focuses and scrolls the updated time list below the header.
- Announcements precede available-day summaries.
- Professor booking calendar counts booked students, including group members; canceled/completed bookings are excluded. Availability calendars retain available-slot counts.
- Student booking pages omit data export, and export endpoints enforce staff permissions. Personal calendar export remains available.

Validation: 279 pytest tests passed with RUN_E2E and isolated PostgreSQL enabled (one existing Starlette deprecation warning); Ruff passed; dependency audit reported no known vulnerabilities. PNGs for site, authenticated survey, and anonymous survey decoded to the expected URLs. Mobile browser screenshots reviewed. Real Android gallery/native file sharing is not verified.

No database migration or paid resource change. Rollback: redeploy cb4a3c9ce4eff9817033bc6b7ba8215fa24dbc4f. Production student records were not modified for testing.
