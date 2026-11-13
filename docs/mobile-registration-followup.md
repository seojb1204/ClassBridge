# Mobile registration follow-up

The reported screenshot contains the lecture action below the announcement and available-day summary, immediately above the bottom tabs. This is a discoverability failure, not a missing API.

- Keep the existing **상담 등록** navigation entry. Inside it, choose **상담 가능 시간** or **강의**. Both use the same timetable.
- Put **+ 강의 추가** in the schedule page header as a direct shortcut to the lecture form.
- Preserve unsaved values when changing registration type within the page.
- Keep consultation preview, overlap protections, weekly repeats, and lecture update/delete unchanged.
- Match HTML background, theme meta, and manifest theme/background to the warm paper colour.

## Device boundary

The screenshot's blue area is Android's three-button system navigation bar, below the web app's correctly themed bottom tabs. HTML/manifest colours are requests to the browser, not direct control of that OS area. Existing installed WebAPKs can update separately from web page assets. Do not claim a desktop mobile viewport proves that the actual Samsung system bar has changed, and do not ask users to clear data or reinstall as a first step.

Reference: https://web.dev/articles/manifest-updates (installed manifest updates) and https://developer.chrome.com/docs/lighthouse/pwa/themed-omnibox (theme colour).

Local regression covers professor/admin registration at 390px and 360px, first-viewport shortcut position, type switching and preservation, and PC/mobile lecture create/edit/delete. Actual S24+ system bar requires device observation.
