#!/usr/bin/env bash
#
# IRIS v3.0.0-beta database migration: PostgreSQL 12 -> 18
#
# This script performs a logical dump-and-restore migration of the IRIS
# database volume. It is designed for the docker-compose deployment and
# never destroys the original PG12 volume — you can roll back at any time
# by reverting docker-compose.yml and pointing back at the preserved
# volume.
#
# It is SAFE to re-run: each step checks state before acting.
#
# What it does (in order):
#   1. Sanity-checks: docker available, compose project present, db service stopped.
#   2. Snapshots the existing db_data volume to a tarball on the host
#      (cold backup — strongest rollback guarantee, no data loss possible).
#   3. Boots a temporary postgres:12-alpine container against the OLD volume
#      and runs pg_dumpall to a host-side .sql file.
#   4. Renames the old volume to <project>_db_data_pg12_backup (preserved).
#   5. Creates a fresh empty volume that the new PG18 image will initialise.
#   6. Boots a temporary postgres:18-alpine container against the new volume,
#      waits for it to be ready, then restores the dump.
#   7. Stops the temporary container. The next `docker compose up` will
#      bring the new iriswebapp_db (PG18) online with all data restored.
#
# Rollback: see upgrade_to_3.0.0.md.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Compose project name — derived the same way docker compose does (basename
# of the project directory, lowercased, non-alnum stripped). Override with
# COMPOSE_PROJECT_NAME in your .env if you use a custom one.
DEFAULT_PROJECT="$(basename "${PROJECT_ROOT}" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')"
COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-${DEFAULT_PROJECT}}"

OLD_VOLUME="${COMPOSE_PROJECT}_db_data"
BACKUP_VOLUME="${COMPOSE_PROJECT}_db_data_pg12_backup"
NEW_VOLUME="${OLD_VOLUME}"            # final name the compose file expects
DUMP_DIR="${PROJECT_ROOT}/upgrades/backups"
TS="${MIGRATION_TIMESTAMP:-$(date +%Y%m%d-%H%M%S)}"
DUMP_FILE="${DUMP_DIR}/iris_pg12_dump_${TS}.sql"
TAR_FILE="${DUMP_DIR}/iris_pg12_volume_${TS}.tar.gz"

OLD_IMAGE="postgres:12-alpine"
NEW_IMAGE="postgres:18-alpine"

TMP_OLD_CTR="iris_pg12_migrate_dump_${TS}"
TMP_NEW_CTR="iris_pg18_migrate_restore_${TS}"

# Load .env so we pick up POSTGRES_USER / POSTGRES_PASSWORD that the
# original cluster was initialised with.
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env"
    set +a
fi

: "${POSTGRES_USER:?POSTGRES_USER must be set (check .env)}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set (check .env)}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log()  { printf '\033[1;34m[migrate]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[migrate]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[migrate]\033[0m %s\n' "$*" >&2; exit 1; }

cleanup() {
    docker rm -f "${TMP_OLD_CTR}" >/dev/null 2>&1 || true
    docker rm -f "${TMP_NEW_CTR}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

volume_exists() {
    docker volume inspect "$1" >/dev/null 2>&1
}

ensure_no_iris_db_running() {
    if docker ps --format '{{.Names}}' | grep -qx 'iriswebapp_db'; then
        die "iriswebapp_db is still running. Stop the stack first: \`docker compose down\`"
    fi
}

# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

step_preflight() {
    log "Pre-flight checks"
    command -v docker >/dev/null || die "docker not found in PATH"
    ensure_no_iris_db_running
    mkdir -p "${DUMP_DIR}"

    if ! volume_exists "${OLD_VOLUME}"; then
        if volume_exists "${BACKUP_VOLUME}"; then
            die "Old volume ${OLD_VOLUME} missing but ${BACKUP_VOLUME} exists — looks like a previous run was interrupted after step 4. Inspect manually before continuing."
        fi
        die "Expected volume ${OLD_VOLUME} not found. Set COMPOSE_PROJECT_NAME if your project is named differently."
    fi

    # Detect that the volume actually contains a PG12 cluster — if PG_VERSION
    # already says 18 the migration was done; bail out so we don't double-run.
    local pgver
    pgver="$(docker run --rm -v "${OLD_VOLUME}:/var/lib/postgresql/data" "${OLD_IMAGE}" \
        sh -c 'cat /var/lib/postgresql/data/PG_VERSION 2>/dev/null || true')"
    if [[ -z "${pgver}" ]]; then
        die "Volume ${OLD_VOLUME} does not look like a Postgres data directory (no PG_VERSION file)."
    fi
    if [[ "${pgver}" != "12" ]]; then
        die "Volume ${OLD_VOLUME} reports PG_VERSION=${pgver}, expected 12. Aborting — this script is only for the 12 → 18 jump."
    fi

    log "OK — found PG12 cluster in volume ${OLD_VOLUME}"
}

step_cold_tar_backup() {
    if [[ -f "${TAR_FILE}" ]]; then
        log "Cold tar backup already exists at ${TAR_FILE} — skipping"
        return
    fi
    log "Creating cold tarball backup of ${OLD_VOLUME} → ${TAR_FILE}"
    docker run --rm \
        -v "${OLD_VOLUME}:/data:ro" \
        -v "${DUMP_DIR}:/backup" \
        alpine:3.20 \
        sh -c "cd /data && tar czf /backup/$(basename "${TAR_FILE}") ."
    log "Cold backup written ($(du -h "${TAR_FILE}" | cut -f1))"
}

step_dump_logical() {
    if [[ -s "${DUMP_FILE}" ]]; then
        log "Logical dump already exists at ${DUMP_FILE} — skipping"
        return
    fi
    log "Starting temporary PG12 container to take a logical dump"
    docker run -d --rm \
        --name "${TMP_OLD_CTR}" \
        -v "${OLD_VOLUME}:/var/lib/postgresql/data" \
        -e POSTGRES_USER="${POSTGRES_USER}" \
        -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
        "${OLD_IMAGE}" >/dev/null

    log "Waiting for PG12 to accept connections"
    for i in $(seq 1 60); do
        if docker exec "${TMP_OLD_CTR}" pg_isready -U "${POSTGRES_USER}" >/dev/null 2>&1; then
            break
        fi
        sleep 1
        if [[ "$i" -eq 60 ]]; then
            die "PG12 did not become ready within 60s"
        fi
    done

    log "Running pg_dumpall → ${DUMP_FILE}"
    # --clean so the restore is idempotent. --if-exists avoids errors when
    # DROP targets do not exist in the fresh cluster.
    docker exec "${TMP_OLD_CTR}" \
        pg_dumpall -U "${POSTGRES_USER}" --clean --if-exists > "${DUMP_FILE}"

    log "Stopping temporary PG12 container"
    docker stop "${TMP_OLD_CTR}" >/dev/null
    log "Logical dump written ($(du -h "${DUMP_FILE}" | cut -f1))"
}

step_swap_volumes() {
    if volume_exists "${BACKUP_VOLUME}"; then
        log "Backup volume ${BACKUP_VOLUME} already exists — swap was done in a prior run, skipping"
        return
    fi

    log "Renaming ${OLD_VOLUME} → ${BACKUP_VOLUME} (copy + remove original)"
    # Docker has no native rename for volumes; we create a new named volume
    # and copy contents. The original is then removed.
    docker volume create "${BACKUP_VOLUME}" >/dev/null
    docker run --rm \
        -v "${OLD_VOLUME}:/from:ro" \
        -v "${BACKUP_VOLUME}:/to" \
        alpine:3.20 \
        sh -c 'cd /from && cp -a . /to/'
    docker volume rm "${OLD_VOLUME}" >/dev/null
    log "Original PG12 data preserved as volume ${BACKUP_VOLUME}"
}

step_restore_to_pg18() {
    # Compose will create the volume on `up`, but we want to restore now
    # so the first compose-managed boot is clean and triggers no init scripts.
    if ! volume_exists "${NEW_VOLUME}"; then
        log "Creating empty volume ${NEW_VOLUME} for PG18"
        docker volume create "${NEW_VOLUME}" >/dev/null
    fi

    # If the volume was already initialised as PG18 from a previous failed
    # run we want to wipe it before re-restoring. We look inside the
    # `pgdata` sub-path because that's where PG18 actually stores its
    # cluster (see the PGDATA env var below for why).
    local existing_ver
    existing_ver="$(docker run --rm -v "${NEW_VOLUME}:/var/lib/postgresql/data" "${NEW_IMAGE}" \
        sh -c 'cat /var/lib/postgresql/data/pgdata/PG_VERSION 2>/dev/null || true')"
    if [[ -n "${existing_ver}" && "${existing_ver}" != "18" ]]; then
        die "${NEW_VOLUME} contains PG_VERSION=${existing_ver} — refusing to overwrite. Inspect manually."
    fi

    log "Starting temporary PG18 container to receive the restore"
    # PGDATA points at a sub-path inside the mounted volume to satisfy
    # PG18's "PGDATA must not equal the mountpoint" check. This matches
    # the compose service so the volume the restore writes is the same
    # layout the running iriswebapp_db will pick up.
    docker run -d --rm \
        --name "${TMP_NEW_CTR}" \
        -v "${NEW_VOLUME}:/var/lib/postgresql/data" \
        -v "${DUMP_DIR}:/dumps:ro" \
        -e POSTGRES_USER="${POSTGRES_USER}" \
        -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
        -e PGDATA=/var/lib/postgresql/data/pgdata \
        "${NEW_IMAGE}" >/dev/null

    log "Waiting for PG18 to accept connections"
    for i in $(seq 1 60); do
        if docker exec "${TMP_NEW_CTR}" pg_isready -U "${POSTGRES_USER}" >/dev/null 2>&1; then
            break
        fi
        sleep 1
        if [[ "$i" -eq 60 ]]; then
            die "PG18 did not become ready within 60s"
        fi
    done

    log "Restoring dump into PG18"
    # ON_ERROR_STOP so a partial restore aborts loudly instead of silently
    # leaving the new cluster in a half-state.
    docker exec -i "${TMP_NEW_CTR}" \
        psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d postgres \
        -f "/dumps/$(basename "${DUMP_FILE}")"

    log "Stopping temporary PG18 container"
    docker stop "${TMP_NEW_CTR}" >/dev/null
    log "Restore complete"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

log "IRIS DB migration: PostgreSQL 12 → 18"
log "Project: ${COMPOSE_PROJECT}"
log "Old volume: ${OLD_VOLUME}"
log "Backup volume (will be created): ${BACKUP_VOLUME}"
log "Dump/tarball directory: ${DUMP_DIR}"

step_preflight
step_cold_tar_backup
step_dump_logical
step_swap_volumes
step_restore_to_pg18

log "Done. You can now start IRIS v3.0.0-beta with: docker compose up -d"
log "Original PG12 data is preserved in volume '${BACKUP_VOLUME}'"
log "Cold tarball backup: ${TAR_FILE}"
log "Logical dump: ${DUMP_FILE}"
log "Once you have verified the new stack, you can reclaim space with:"
log "    docker volume rm ${BACKUP_VOLUME}"
log "    rm '${TAR_FILE}' '${DUMP_FILE}'"
