# Editorial Campus (C)

User-selected visual direction. Implements warm ivory paper (#f7f3ec), dark ink,
terracotta emphasis (#a64419), serif headings and ClassBridge wordmark, thin rules,
quiet flat surfaces, and restrained corner radii. Body text stays system sans-serif
for Korean form/data readability. No external font request or font license dependency.
The selected concept image is a reference, not production content: sample appointments,
image spelling errors, and demo labels are not inserted into the service.

## Preserved
All routes, APIs, authorization, notification settings, calendar semantics, slot creation,
booking changes, mobile daily/list views, survey publishing/results, anonymous suggestion
privacy notice, trash-selection flows, help, and admin settings remain intact.
Student/professor/admin navigation retains existing names. This change does not add a
lecture schedule or mutate production data. Existing semantic green/red status colours
remain distinct from the orange primary action and booked-slot state.

## Accessibility
Normal text palette regression checks enforce WCAG AA 4.5:1; focus/control boundaries
are checked at 3:1. Main text/background is 13.5:1; muted text/background 5.7:1;
primary/background 5.48:1. Focus-visible rings are retained. Skip-to-content prevents
hash routing and moves focus directly to main. Reduced-motion preference is honoured.
Mobile tap targets and bottom-safe-area navigation remain available. Colour alone is
not the only status signal: existing labels and counts remain.

## Verification
`tests/test_editorial_palette.py` checks design tokens.
`tests/e2e/test_editorial_campus.py` uses isolated fixture accounts for professor, admin,
student at desktop 1366px, mobile 390px, and tablet 768px. It captures each role's main
views, checks horizontal overflow, preserved brand/navigation, and the skip link.
Existing browser suites cover booking, survey, inbox, privacy and destructive flows.
Run full CI before deployment; screenshot review remains required, not inferred from CSS.

Reference: MDN colour contrast and focus-visible guidance, retrieved with Context7
(`/mdn/content`), 2026-11-13. This is targeted documentation, not an automated code audit.
