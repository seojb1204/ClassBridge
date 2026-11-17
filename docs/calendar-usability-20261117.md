# Calendar and mobile navigation usability

- Reservation management starts in weekly calendar; list/activity modes remain available.
- Shared mobile header places calendar/list selector above compact previous/date/next navigation.
- Consultation availability uses wrapping three-column compact cards (two columns below 350px), no horizontal scrolling.
- Removed redundant registration paragraph; registration tab is 상담; menu group is 설문·건의.
- Mobile More menu opens above the measured bottom tab bar, including safe-area height. Escape/outside click closes; Escape returns focus. Logout and role-filtered destinations remain available. Desktop menu unchanged.
- Approved gesture tuning: 50px distance OR minimum 25px at average speed >= 0.4px/ms; 10px direction lock with 1.3 horizontal/vertical ratio. These are product test settings, not research-validated universal constants. Cancellation, vertical scrolling, pinch and reduced-motion remain supported. Click suppression 250ms; settle animation 200ms.

## Validation
- 61 unit tests passed; 132 deterministic gesture checks; 10 slot-label regressions; cache regression script passed.
- New viewport E2E tests cover 360/390/1280 widths, default view, menu placement/focus, compact availability and labels. Updated old gesture regression expectations for the approved smaller threshold.
- Local Chromium attempts blocked by environment `socket() failed: Operation not permitted`, including approved escalated retry. Browser tests require CI or another permitted test environment. Not verified on a real phone or authenticated deployed account here.
