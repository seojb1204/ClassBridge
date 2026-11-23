# Calendar / notification / consultation input release

## Scope
- Calendar is the initial reservation-management view; list and activity remain.
- Mobile date navigation is below calendar/list toggle. Available days wrap into a compact grid.
- Mobile More opens directly above the real bottom navigation and retains role-specific destinations.
- Notification rows are single keyboard-accessible links. The server resolves owned, arrived notifications to exact existing booking events; cancelled bookings are opened without substituting another attendee. Missing legacy targets are explicit.
- A temporary static outline identifies the target; no flashing is used.
- Consultation input accepts deterministic relative dates and common Korean formatting. AI providers are not connected.

## Data and security
No schema migration, production data mutation, permission expansion, new provider, or secret is introduced. Existing role authorization, preview, conflicts, CSRF and explicit registration confirmation remain. Existing pale-green reserved and empty-slot colors are unchanged.

## AI follow-up, not activated
Recommended later boundary: parse a sentence into a proposed structured schedule, show uncertainties, then use the same server preview and explicit save confirmation. Never execute commands returned by a model.
Owner decisions before activation: provider/account, monthly spending cap, whether a sentence may leave ClassBridge, and acceptable retention terms. Prefer date/time/location-only inputs; exclude student names, emails and consultation contents. Credentials belong in server-side secret storage, not chat or frontend code. Ambiguous dates or destructive/exclusion instructions must require a user decision rather than be silently guessed.

## Verification limits
Local Chromium cannot start in this execution sandbox (socket permission); GitHub CI runs real Chromium and PostgreSQL. Browser viewport tests are not real-phone touch measurements. Swipe values (50px, 25px +0.4px/ms, 10px intent with 1.3 axis ratio) are trial settings, not universally proven scientific thresholds. Review actual device feedback after deployment.
