# Calendar swipe feedback

References reviewed 2026-11-14:
- FullCalendar official buttons: https://fullcalendar.io/docs/buttons — explicit previous/next labels and icons, accessible hints; retain existing buttons as keyboard alternatives.
- Material Design official gestures: https://m1.material.io/patterns/gestures.html — distinguish touch feedback from action commitment and allow return before a threshold.

Implementation: rightward pull reveals a left-side ← 이전 주로; leftward pull reveals right-side → 다음 주로. Warm Editorial Campus surface and terracotta readiness highlight. Short pulls show an arrow before room exists for the text. Reduced-motion keeps a stationary hint and does not translate the grid. The decorative hint is hidden from assistive technology and cannot receive clicks; the named week-navigation buttons remain available. Release threshold, elastic displacement and return duration are unchanged. Cancel hides the hint without navigation. Test at 360/390px and reduced-motion modes, plus existing vertical scrolling and time-slot actions.
