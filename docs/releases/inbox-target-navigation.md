# Notification destination integration

- Whole notification is now one native anchor (keyboard/Enter, no nested read/detail buttons). Read-all remains. A failed mark-read does not navigate or hide unread state.
- Booking/custom-reminder links resolve `/#/inbox/:notificationId` using `GET /api/inbox/:id/target`. Existing `booking-event-{BookingEvent.id}` keys resolve the exact booking, including cancelled and historical dates. No DB schema migration/backfill and no external AI call.
- API requires booking-manage and professor/admin role, an owned arrived inbox record. Another staff account cannot resolve the notification. The notification listing remains content-minimal; booking details come only from the authorized target call.
- `profBookings.openNotification(root, booking)` selects its current KST week/date then opens the existing detail dialog with *only that booking*, not the first student in a group slot. Modified bookings open their latest current date/state; this is not an immutable event-time snapshot.
- Missing legacy event key/deleted target: explicit unavailable message and booking-list link, never guesses a target. Personal reminders show their saved body. Suggestions remain aggregate notifications and link to the suggestions inbox, not an invented individual item.
- Detail receives static terracotta outline/pale tint for 2800ms; no blinking, animation disabled for reduced-motion. Normal dialog focus trap retained. Reopening the same target from the bell rerenders safely.
- UI integration hooks in main.js (one route), prof-bookings.js (guard/export/modal highlight), appended CSS. Preserve parallel UI agent's default calendar and navigation layout changes.
- Browser tests use mocked target/calendar data plus real local app routing; backend tests use temporary SQLite. This does not prove production identity access or physical-device behavior.
