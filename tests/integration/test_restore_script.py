"""Exercise shell refusal paths with fake tools; never connect to a database."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or (
    str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe")
    if os.name == "nt" else None
)


def shell_path(path: Path) -> str:
    value = path.as_posix()
    return f"/{value[0].lower()}{value[2:]}" if os.name == "nt" else value


@pytest.mark.parametrize("scenario", ["success", "wrong_host", "occupied", "decrypt_fail", "restore_fail"])
def test_restore_pipeline_refuses_unsafe_or_failed_operations(tmp_path, scenario):
    if not BASH or not Path(BASH).exists():
        pytest.skip("Bash unavailable; CI runs the shell safety tests")
    binary = tmp_path / "bin"
    binary.mkdir()
    stubs = {
        "psql": '''case "$*" in
  *current_database*) echo classbridge_restore_trial ;;
  *pg_namespace*) echo "${OBJECT_COUNT:-0}" ;;
  *version_num*) echo 0004 ;;
  *) exit 90 ;;
esac
''',
        "gpg": '''if [[ "${DECRYPT_FAIL:-0}" == 1 ]]; then exit 3; fi
printf 'fixture archive'
''',
        "pg_restore": '''[[ "$*" == *--single-transaction* ]] || exit 91
[[ "$*" == *--exit-on-error* ]] || exit 92
[[ "$*" == *--dbname=* ]] || exit 93
cat >/dev/null
touch "$RESTORE_MARKER"
exit "${RESTORE_FAIL:-0}"
''',
    }
    for name, content in stubs.items():
        target = binary / name
        target.write_text("#!/usr/bin/env bash\n" + content, encoding="utf-8", newline="\n")
        target.chmod(0o700)
    archive = tmp_path / "fixture.gpg"
    archive.write_bytes(b"fake encrypted fixture")
    marker = tmp_path / "restore-called"
    env = {**os.environ,
           "DATABASE_URL_DIRECT": "postgresql://source.example/neondb",
           "RESTORE_DATABASE_URL": "postgresql://restore.example/classbridge_restore_trial",
           "EXPECTED_RESTORE_HOST": "restore.example",
           "EXPECTED_RESTORE_DATABASE": "classbridge_restore_trial",
           "PYTHON_BIN": Path(sys.executable).as_posix(),
           "STUB_BIN": shell_path(binary), "ARCHIVE": shell_path(archive),
           "SCRIPT": shell_path(ROOT / "scripts/verify_neon_restore.sh"),
           "RESTORE_MARKER": shell_path(marker),
           "OBJECT_COUNT": "1" if scenario == "occupied" else "0",
           "DECRYPT_FAIL": "1" if scenario == "decrypt_fail" else "0",
           "RESTORE_FAIL": "4" if scenario == "restore_fail" else "0"}
    if scenario == "wrong_host":
        env["EXPECTED_RESTORE_HOST"] = "different.example"
    result = subprocess.run([BASH, "-c", 'export PATH="$STUB_BIN:$PATH"; bash "$SCRIPT" "$ARCHIVE"'],
                            env=env, capture_output=True, text=True, timeout=20)
    if scenario == "success":
        assert result.returncode == 0, result.stderr
        assert marker.exists()
        assert "Restore rehearsal completed" in result.stdout
    else:
        assert result.returncode != 0
        assert "Restore rehearsal completed" not in result.stdout
        assert marker.exists() == (scenario == "restore_fail")
