#!/usr/bin/env bash
# Restore rehearsal into a dedicated EMPTY test database.
# Never target staging's neondb or the production branch/database.
set -euo pipefail
umask 077
: "${RESTORE_DATABASE_URL:?Provide a disposable RESTORE database connection string}"
: "${1:?Usage: ./scripts/verify_neon_restore.sh encrypted.dump.gpg}"

# Check the explicitly approved destination before any network or decryption work.
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
"${PYTHON_BIN:-python3}" "$script_dir/validate_restore_target.py"

for cmd in psql pg_restore gpg; do
  command -v "$cmd" >/dev/null || { echo "$cmd is missing" >&2; exit 2; }
done

archive="$1"
test -s "$archive" || { echo "Encrypted archive not found" >&2; exit 2; }

# Confirm DB identity and emptiness before decrypting and restoring.
database_name="$(PGDATABASE="$RESTORE_DATABASE_URL" psql -X -w -v ON_ERROR_STOP=1 -Atqc "SELECT current_database()")"
if [[ "$database_name" != "$EXPECTED_RESTORE_DATABASE" ]]; then
  echo "Connected database does not match approved destination; no changes made" >&2
  exit 2
fi
object_count="$(PGDATABASE="$RESTORE_DATABASE_URL" psql -X -w -v ON_ERROR_STOP=1 -Atqc \
  "SELECT (SELECT count(*) FROM pg_namespace WHERE nspname NOT IN ('public','information_schema') AND nspname NOT LIKE 'pg_%') + (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname='public') + (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='public') + (SELECT count(*) FROM pg_type t JOIN pg_namespace n ON t.typnamespace=n.oid WHERE n.nspname='public')")"
if [[ "$object_count" != "0" ]]; then
  echo "Restore target has existing objects; refusing to modify it" >&2
  exit 2
fi

# Verify the encrypted stream before allowing a restore to write anything.
gpg --batch --decrypt -- "$archive" >/dev/null
echo "Starting restore rehearsal in the approved separate empty database"
gpg --batch --decrypt -- "$archive" |
  pg_restore --no-password --no-owner --no-acl --dbname="$RESTORE_DATABASE_URL" \
    --exit-on-error --single-transaction

PGDATABASE="$RESTORE_DATABASE_URL" psql -X -w -v ON_ERROR_STOP=1 -Atqc \
  "SELECT version_num FROM public.alembic_version LIMIT 1"
echo "Restore rehearsal completed. Compare expected counts and application behavior."
