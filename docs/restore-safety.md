# Isolated restore rehearsal

Only run a real-data rehearsal after approval of the source, destination, key
custody, storage location, retention and cost. Do not use a production or staging
application database as the destination. The script does not create databases.

Required environment variables (never commit their secret values):

- `DATABASE_URL_DIRECT`: approved source PostgreSQL URI.
- `RESTORE_DATABASE_URL`: dedicated empty restore PostgreSQL URI.
- `EXPECTED_RESTORE_HOST`: explicitly approved target hostname.
- `EXPECTED_RESTORE_DATABASE`: exact name, starting with `classbridge_restore_`.
- `PYTHON_BIN`: optional Python 3 executable; default `python3`.

Run `bash scripts/verify_neon_restore.sh /path/to/encrypted.dump.gpg`.
Use a PostgreSQL client compatible with the source server and the intended GPG key.
Do not enable shell tracing: connection arguments contain credentials.

Before connecting, the validator rejects mismatched targets, pooled connections,
connection-override URI parameters and a source/target hostname match. Hostname
checks are not proof of infrastructure isolation: confirm the selected endpoints
and DNS aliases independently. Use a dedicated role with access only to the restore
database, and ensure no other clients can write during the rehearsal.

Before decrypting, the script checks the connected database name and refuses
non-system schemas or existing public relations, functions and types. It validates
decryption first, then restores with `--single-transaction` and `--exit-on-error`.
The archive must be a trusted, immutable file for the duration of both reads.
Keep the source unchanged during the comparison window or compare against a
manifest captured from the same backup snapshot.

A successful restore is not yet a recovery certification. Independently compare
migration version, table counts, constraints, sequences and private record hashes,
then verify application reads and reservation invariants on the isolated target.
Never print private rows or credentials. On any failure, report failure and inspect
the disposable target; do not automatically delete or retry over existing data.

Tests distinguish URI validation, fake-tool shell refusal paths, and actual
PostgreSQL/GPG recovery. Fake-tool success does not prove a real encrypted backup
or restore. No real-data recovery is performed by the normal application deploy.
