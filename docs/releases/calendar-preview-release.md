# Calendar preview and professor notification status

Registration preview shows every planned date in a month calendar, with month navigation and a complete time list for the selected date. Registration folds the form and reveals the chosen date's calendar/list. Booking management exposes a read-only notification summary scoped to the signed-in staff recipient, including configuration, this session's push registration, pending/action-required counts and last send timestamp. Delivery is explicitly not claimed as receipt/read confirmation. Requested suggestion warning text is removed.

Validation: local full run passed 278 tests; three test expectations were updated for the approved collapsed form/removed copy and explicit simulated 503 handling, then all three passed. Ruff and whitespace checks passed. Mobile/desktop screenshots and year-boundary navigation checked. GitHub CI runs the complete suite before merging.

No DB migration, credentials change, real email send or new cost. Rollback to 5297c52787cf02f105dbc5bc74fdba7cf3bb87c0. Actual phone/email receipt is not verified by this UI change.
