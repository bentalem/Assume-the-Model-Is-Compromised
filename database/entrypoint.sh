#!/bin/sh
# Migration job entrypoint.
#
# Runs once and exits (SP-BUILD-001 §6). Applies forward migrations, then permission and RLS smoke
# tests. Runtime services never receive the credential this job uses.
set -eu

log() { printf '[migrate] %s\n' "$*"; }

read_secret() {
  file="$1"
  [ -r "$file" ] || { log "FATAL: secret file not readable: $file"; exit 1; }
  # Trim trailing newline only; a password may legitimately contain spaces.
  tr -d '\n\r' < "$file"
}

BOOTSTRAP_PASSWORD="$(read_secret "$BOOTSTRAP_PASSWORD_FILE")"
MIGRATOR_PASSWORD="$(read_secret "$MIGRATOR_PASSWORD_FILE")"
API_PASSWORD="$(read_secret "$API_PASSWORD_FILE")"
WORKER_PASSWORD="$(read_secret "$WORKER_PASSWORD_FILE")"
AUDITOR_PASSWORD="$(read_secret "$AUDITOR_PASSWORD_FILE")"
RANGE_PASSWORD="$(read_secret "$RANGE_PASSWORD_FILE")"

export PGHOST="$DATABASE_HOST"
export PGPORT="$DATABASE_PORT"
export PGDATABASE="$DATABASE_NAME"
export PGUSER="$BOOTSTRAP_USER"
export PGPASSWORD="$BOOTSTRAP_PASSWORD"

log "waiting for postgres at $PGHOST:$PGPORT"
i=0
until pg_isready -q; do
  i=$((i + 1))
  [ "$i" -lt 60 ] || { log "FATAL: postgres not ready after 60 attempts"; exit 1; }
  sleep 1
done

applied() {
  psql -tAX -c "SELECT 1 FROM app.schema_migrations WHERE version = '$1'" 2>/dev/null | grep -q 1
}

# ------------------------------------------------------------------------------------------------
# 0001 creates the roles, so it runs with role passwords passed as psql variables and is guarded by
# the existence of the schema_migrations table rather than a row in it.
# ------------------------------------------------------------------------------------------------
if psql -tAX -c "SELECT to_regclass('app.schema_migrations')" | grep -q app.schema_migrations; then
  log "0001_roles_and_schema already applied"
else
  log "applying 0001_roles_and_schema"
  psql -v ON_ERROR_STOP=1 \
       -v migrator_password="$MIGRATOR_PASSWORD" \
       -v api_password="$API_PASSWORD" \
       -v worker_password="$WORKER_PASSWORD" \
       -v auditor_password="$AUDITOR_PASSWORD" \
       -v range_password="$RANGE_PASSWORD" \
       -f /migrations/0001_roles_and_schema.sql
  psql -v ON_ERROR_STOP=1 -c "INSERT INTO app.schema_migrations (version) VALUES ('0001_roles_and_schema')"
fi

# The bootstrap user must be able to SET ROLE to the migration role for the remaining files.
psql -v ON_ERROR_STOP=1 -qc "GRANT sp_migrator_role TO CURRENT_USER" >/dev/null

applied_count=0
for file in /migrations/*.sql; do
  [ -f "$file" ] || continue
  version="$(basename "$file" .sql)"

  # 0001 is handled above, because it creates the roles the rest depend on.
  [ "$version" = "0001_roles_and_schema" ] && continue

  if applied "$version"; then
    log "skip $version (already applied)"
    continue
  fi
  log "applying $version"
  # Role passwords are passed to every migration, not only to 0001. A migration that creates a role
  # needs them, and one rule here is better than a second special case in this loop.
  psql -v ON_ERROR_STOP=1 \
       -v migrator_password="$MIGRATOR_PASSWORD" \
       -v api_password="$API_PASSWORD" \
       -v worker_password="$WORKER_PASSWORD" \
       -v auditor_password="$AUDITOR_PASSWORD" \
       -v range_password="$RANGE_PASSWORD" \
       -f "$file"
  applied_count=$((applied_count + 1))
done

# A migration set that matches nothing is a packaging fault, not an empty changeset. Failing here
# is what stops a silently-unmigrated database from reaching the smoke tests and the API.
migration_files="$(find /migrations -name '*.sql' | wc -l)"
recorded="$(psql -tAX -c 'SELECT count(*) FROM app.schema_migrations' | tr -d ' ')"
if [ "$recorded" -ne "$migration_files" ]; then
  log "FATAL: $migration_files migration file(s) present but $recorded recorded as applied"
  exit 4
fi
log "applied $applied_count migration(s); $recorded of $migration_files recorded"

# ------------------------------------------------------------------------------------------------
# Seeds. Local only, and never on top of a database that already holds non-seed data.
# ------------------------------------------------------------------------------------------------
if [ "${SEED_LOCAL_DATA:-false}" = "true" ]; then
  for file in /seeds/*.sql; do
    [ -f "$file" ] || continue
    log "seeding $(basename "$file")"
    psql -v ON_ERROR_STOP=1 -f "$file"
  done
fi

# ------------------------------------------------------------------------------------------------
# Permission and RLS smoke tests. The job fails if any of these regress (SP-BUILD-001 §6 step 5).
# ------------------------------------------------------------------------------------------------
log "running permission and RLS smoke tests"
psql -v ON_ERROR_STOP=1 -f /tests/permissions_smoke.sql

log "schema version: $(psql -tAX -c "SELECT max(version) FROM app.schema_migrations")"
log "done"
