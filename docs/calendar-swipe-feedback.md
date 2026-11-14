# Calendar swipe feedback

References reviewed 2026-11-14:
- FullCalendar official buttons: https://fullcalendar.io/docs/buttons — explicit previous/next labels and icons, accessible hints; retain existing buttons as keyboard alternatives.
- Material Design official gestures: https://m1.material.io/patterns/gestures.html — distinguish touch feedback from action commitment and allow return before a threshold.

Implementation: rightward pull reveals a left-side ← 이전 주로; leftward pull reveals right-side → 다음 주로. Warm Editorial Campus surface and terracotta readiness highlight. Short pulls show an arrow before room exists for the text. Reduced-motion keeps a stationary hint and does not translate the grid. The decorative hint is hidden from assistive technology and cannot receive clicks; the named week-navigation buttons remain available. Release threshold, elastic displacement and return duration are unchanged. Cancel hides the hint without navigation. Test at 360/390px and reduced-motion modes, plus existing vertical scrolling and time-slot actions.

## 2026-11-14 independent follow-up candidate (not deployed)

The deployed module matched staging 9137983 byte-for-byte. Handler replay found
that the first 12px movement classified ambiguous diagonals (12,10 or 10,12)
as vertical forever, even when followed by a 230px horizontal pull. Desktop
mouse drag is intentionally ignored and remains unchanged in this candidate.

The candidate leaves ambiguous angles undecided until one direction dominates
by 1.3x; clearly vertical movement and browser pointercancel remain untouched.
The ordinary 52% / 160–210px trigger, visual curve, spring duration, no-velocity
rule, and reduced-motion behavior stay unchanged for edge-origin pulls. For a
central start only, the trigger is capped at 85% of the runway to that calendar
edge, with a 120px minimum to reject tiny near-edge flicks. Hint readiness uses
the exact same per-direction threshold as release.

`node scripts/test-week-swipe.mjs`: 112 deterministic handler checks pass;
the unmodified deployed module fails the diagonal regression. These tests mock
DOM events and DO NOT establish real browser/native touch behavior. New native
Chromium tests cover center-origin and diagonal-start motions at 360/390px;
these and existing vertical chaining / slot taps MUST pass before deployment.
This executor cannot start Chromium (socket EPERM even after execution retry).
Ruff passed, JS syntax and Python test-file compilation passed.
Real Galaxy S24+ / Samsung Internet / installed PWA remain unverified.

Local pytest: 374 passed, 160 skipped (browser/PostgreSQL not run).
