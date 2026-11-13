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

## Mobile timetable follow-up

The original renderer deliberately changed to a single-day list below 720px; the staff slot page additionally disabled the view selector. Replace this restriction with Week / 3 days / List. Week remains the default, with the same chronological grid and event detail actions as desktop; 3 days provides more readable labels without losing the time axis. Announcements and available-day summaries remain accessible in a disclosure above the staff calendar rather than occupying its first screen.

Mobile layout checks must cover 360px and 390px, professor/admin and student roles, all view modes, day/week navigation, minute-precision lecture placement, event details and no body overflow. PC remains a seven-day grid. Consultation and lecture backend rules are unchanged.

The page opts into viewport safe areas and declares the supported light colour scheme. Bottom navigation spacing includes the safe-area inset. This can fix web content/inset colour mismatches, but **does not verify or force the S24+ operating-system navigation-bar colour**. No phone/browser setting is changed. Inspect normal browser versus installed-app launch and actual browser/OneUI versions before attributing the remaining blue strip to cache or browser behaviour.

Official references consulted:
- Google Calendar Android multiple views: https://support.google.com/calendar/answer/6110849?co=GENIE.Platform%3DAndroid
- Samsung Calendar week/day views: https://galaxystore.samsung.com/detail/com.samsung.android.calendar?langCd=ko
- Installed WebAPK metadata update lifecycle: https://web.dev/articles/manifest-updates
- Chromium installed-app navigation-bar theme implementation (not proof of the user's installed browser version): https://chromium.googlesource.com/chromium/src/+/0a6ab4f0e2ce17e572b05400ae6eacd7fc5389f0
