# Flexible consultation sentence input

Deterministic, no AI/provider calls or credentials. `parseSchedule(text, todayKst)`
returns the existing `{date,start,end}` contract plus optional `durationMinutes`,
`breakMinutes`, `repeatWeeks`, `location`. Missing optional properties leave form
values unchanged. The UI displays exact date/time, then the existing server
preview/conflict checks and explicit confirmation remain mandatory.

Supported: no spaces between date/time, Korean hour numbers and half hours,
오늘/내일/모레, 이번주/다음주 plus weekday, 담주/화욜, N분씩, 휴식 N분,
매주 N주, 장소 TOKEN, 상담/등록해줘. Time policy remains 08:00–18:00 and
unqualified 1–6 means afternoon, as already disclosed in the form. Relative dates
are calculated from the existing KST date provider. Dates never silently roll to
a future year. Date/weekday disagreements, bare weekdays, missing end times,
unspecified repeat duration, corrections/deletions/exceptions are rejected with
clarification guidance; partially parsed values are not applied.

Not supported: arbitrary language, multiple independent dates/weekdays in one
sentence, holidays, exclusion rules, overnight windows, multi-word locations.
The user must use explicit fields for these or request a separately specified
feature. Rejection never deletes existing data.

Future AI boundary: AI may propose this structured candidate only. Any future
integration requires provider/budget/privacy decisions, ambiguity handling and
normalization through the same deterministic business/server validation. No
current AI implementation or automatic saving is claimed.

Validation: `node scripts/test_schedule_input.mjs`. Browser E2E test
`test_flexible_sentence_populates_form_without_registering` verifies input
handoff and non-destructive rejection; it must be run in the integrated UI.
