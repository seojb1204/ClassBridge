"""Render the versioned SVG master with Inkscape (development only).

Run: python scripts/render_app_icons.py
Requires Inkscape on PATH. Production only serves the committed PNG assets.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "static" / "icons"


def main():
    for name, size in (("app-editorial-v1-32", 32), ("app-editorial-v1-180", 180),
                       ("app-editorial-v1-192", 192), ("app-editorial-v1-512", 512),
                       ("app-editorial-v1-maskable-512", 512)):
        subprocess.run([
            "inkscape", str(ICONS / "app-editorial-v1.svg"), "--export-type=png",
            f"--export-filename={ICONS / f'{name}.png'}", f"--export-width={size}", f"--export-height={size}",
        ], check=True)


if __name__ == "__main__":
    main()
