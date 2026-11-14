# Editorial Campus app icon

The existing calendar identity now uses the live theme's terracotta `#a64419`
and paper `#f7f3ec`. The SVG master is `static/icons/app-editorial-v1.svg`.
All foreground artwork fits within the central 80% maskable circle, leaving
solid background at the edges for Android launcher masks.

The manifest references new, versioned 192/512/maskable PNG paths. The site
favicon uses 32px and iOS has an explicit 180px apple-touch-icon. The manifest
id, name, scope and start URL are unchanged. Old assets are retained for older
installed clients. No student, reservation, authentication or data behavior changes.

Regenerate PNGs with `python scripts/render_app_icons.py` (Inkscape on PATH).
The script is for development only and adds no runtime dependency.

Existing installed home-screen icons may not refresh immediately because the
browser/OS owns their update schedule. A newly added home-screen shortcut uses
the new asset. Do not promise that an existing iOS or Android installation
changes immediately after deployment. Confirm the new icon before removing any
old shortcut; do not clear app data as a troubleshooting step.
