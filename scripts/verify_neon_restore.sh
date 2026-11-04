#!/usr/bin/env bash
# Restore rehearsal into a dedicated EMPTY test database.
# Never target staging's neondb or the production branch/database.
set -euo pipefail
: "${RESTORE_DATABASE_URL:?Provide a disposable RESTORE database connection string}"
: "${1:?Usage: ./scripts/verify_neon_restore.sh encrypted.dump.gpg}"

for cmd in psql pg_restore gpg; do
  command -v "$cmd" >/dev/null || { echo "$cmd is missing" >&2; exit 2; }
done

archive="$1"
test -s "$archive" || { echo "Encrypted archive not found" >&2; exit 2; }

# Confirm DB identity and emptiness before decrypting and restoring.
database_name="$(psql "$RESTORE_DATABASE_URL" -Atqc "SELECT current_database()")"
if [[ "$database_name" != *restore* ]]; then
  echo "Target database name must contain 'restore'; no changes made" >&2
  exit 2
fi
table_count="$(psql "$RESTORE_DATABASE_URL" -Atqc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")"
if [[ "$table_count" != "0" ]]; then
  echo "Restore target has existing tables; refusing to modify it" >&2
  exit 2
fi

echo "Starting restore rehearsal in a separate empty database"
gpg --batch --decrypt -- "$archive" |
  pg_restore --no-owner --no-acl --exit-on-error --dbname="$RESTORE_DATABASE_URL"

psql "$RESTORE_DATABASE_URL" -Atqc \
  "SELECT version_num FROM public.alembic_version LIMIT 1"
echo "Restore rehearsal completed. Compare expected counts and application behavior."
