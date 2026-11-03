#!/usr/bin/env bash
# Export an encrypted PostgreSQL backup without writing a plaintext dump to disk.
# Requires PostgreSQL client (pg_dump) and a previously imported GPG public key.
set -euo pipefail
umask 077

: "${DATABASE_URL_DIRECT:?Set DATABASE_URL_DIRECT to the staging direct Postgres URI}"
: "${BACKUP_GPG_RECIPIENT:?Set BACKUP_GPG_RECIPIENT to your GPG public key fingerprint}"
: "${BACKUP_DIR:?Set BACKUP_DIR to a secure backup directory}"

command -v pg_dump >/dev/null || { echo "pg_dump is not installed" >&2; exit 2; }
command -v gpg >/dev/null || { echo "gpg is not installed" >&2; exit 2; }
gpg --batch --list-keys "$BACKUP_GPG_RECIPIENT" >/dev/null 2>&1 ||
  { echo "GPG public key is unavailable; aborting" >&2; exit 2; }

mkdir -p -- "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
dest="$BACKUP_DIR/classbridge-staging-$timestamp.dump.gpg"
if [[ -e "$dest" ]]; then
  echo "Backup path exists; refusing overwrite" >&2
  exit 2
fi

# The plaintext dump stays in a pipe, not on disk.
if ! pg_dump --format=custom --no-owner --no-acl "$DATABASE_URL_DIRECT" |
    gpg --batch --yes --trust-model always --encrypt --recipient "$BACKUP_GPG_RECIPIENT" --output "$dest"; then
  rm -f -- "$dest"
  echo "Backup command failed; no backup retained" >&2
  exit 1
fi
test -s "$dest"
echo "Encrypted backup created: $dest"
echo "Verification still required: decrypt and restore into a SEPARATE empty test DB."
