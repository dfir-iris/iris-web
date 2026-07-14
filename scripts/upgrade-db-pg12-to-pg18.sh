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
#      bring the new iris_db (PG18) online with all data restored.
#
# Rollback: see docs/upgrade-to-3.0.0.md.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# This script lives at iris-web/scripts/upgrade-db-pg12-to-pg18.sh in the
# V3 meta-repo. PROJECT_ROOT walks up one directory to iris-web/ which is
# the docker-compose project root (compose file + .env live here). In the
# pre-V3 layout this script lived at iris-backend/upgrades/... and
# PROJECT_ROOT resolved to iris-backend/ — SAME basename ("iris-web"),
# because on legacy installs the compose project was iris-web too. That
# means the derived COMPOSE_PROJECT and volume name stay backward-
# compatible: pre-V3 installs still find their existing iris-web_db_data
# volume without setting COMPOSE_PROJECT_NAME.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Compose project name — derived the same way docker compose does: basename
# of the project directory, lowercased, keeping only [a-z0-9_-]. Hyphens are
# preserved (unlike a naive alnum-only strip). Override with
# COMPOSE_PROJECT_NAME in your .env if you use a custom one.
DEFAULT_PROJECT="$(basename "${PROJECT_ROOT}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-')"
COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-${DEFAULT_PROJECT}}"

OLD_VOLUME="${COMPOSE_PROJECT}_db_data"
BACKUP_VOLUME="${COMPOSE_PROJECT}_db_data_pg12_backup"
NEW_VOLUME="${OLD_VOLUME}"            # final name the compose file expects
# Dumps + cold tarballs land under iris-web/backups/. The backups/ dir is
# already .gitignored in the meta-repo (see iris-web/.gitignore).
DUMP_DIR="${PROJECT_ROOT}/backups"
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
    # Pre-V3 named the db container iriswebapp_db; V3 renamed it to iris_db.
    # Refuse to start the migration if either is still up.
    local names
    names="$(docker ps --format '{{.Names}}' | grep -Ex 'iriswebapp_db|iris_db' || true)"
    if [[ -n "${names}" ]]; then
        die "IRIS db container is still running (${names//$'\n'/ }). Stop the stack first: \`docker compose down\`"
    fi
    # A stopped-but-not-removed container still holds a reference on the
    # volume and blocks the rename step later. `docker compose down` removes
    # it; a bare `docker stop` does not.
    names="$(docker ps -a --format '{{.Names}}' | grep -Ex 'iriswebapp_db|iris_db' || true)"
    if [[ -n "${names}" ]]; then
        die "IRIS db container exists but is stopped (${names//$'\n'/ }) and still holds the volume. Run \`docker compose down\` (not just stop) before retrying."
    fi
}

# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

# Set to 1 by pre-flight when we detect a resume-from-restore state (backup
# volume already holds PG12 data and the logical dump file exists). In that
# state the backup/dump/swap steps are no-ops.
RESUME_FROM_RESTORE=0

# Read the PG_VERSION of a volume's pgdata/ sub-path, or empty string if no
# such file exists. The IRIS compose file runs postgres with PGDATA pointing
# at the pgdata/ sub-path, so PG_VERSION lives one level below the mountpoint.
read_pg_version() {
    local vol="$1"
    docker run --rm -v "${vol}:/var/lib/postgresql/data" "${OLD_IMAGE}" \
        sh -c 'cat /var/lib/postgresql/data/pgdata/PG_VERSION 2>/dev/null || true'
}

# Is the volume mount empty (aside from the mount metadata)? Used to
# distinguish "fresh empty volume" from "populated cluster".
volume_is_empty() {
    local vol="$1"
    local count
    count="$(docker run --rm -v "${vol}:/data" alpine:3.20 \
        sh -c 'ls -A /data | wc -l' 2>/dev/null | tr -d ' ')"
    [[ "${count}" == "0" ]]
}

step_preflight() {
    log "Pre-flight checks"
    command -v docker >/dev/null || die "docker not found in PATH"
    ensure_no_iris_db_running
    mkdir -p "${DUMP_DIR}"

    # Resume path: the backup volume exists and holds PG12 data, and there is
    # at least one dump file in the dump dir. This is the state after the
    # swap step succeeded but the restore step failed or hasn't run yet. We
    # short-circuit to just the restore step below.
    if volume_exists "${BACKUP_VOLUME}"; then
        local backup_ver
        backup_ver="$(read_pg_version "${BACKUP_VOLUME}")"
        local latest_dump
        latest_dump="$(ls -1t "${DUMP_DIR}"/iris_pg12_dump_*.sql 2>/dev/null | head -1)"
        if [[ "${backup_ver}" == "12" && -n "${latest_dump}" ]]; then
            # The remaining restore step reads from ${DUMP_FILE}; re-point it
            # at whatever dump we have on disk so we don't try to create a
            # fresh one against the (now gone) old volume.
            DUMP_FILE="${latest_dump}"
            RESUME_FROM_RESTORE=1
            log "Resuming from post-swap state — backup ${BACKUP_VOLUME} holds PG12 data, using dump ${DUMP_FILE}"
            return
        fi
    fi

    if ! volume_exists "${OLD_VOLUME}"; then
        if volume_exists "${BACKUP_VOLUME}"; then
            die "Old volume ${OLD_VOLUME} missing but ${BACKUP_VOLUME} exists — looks like a previous run was interrupted after step 4 and no dump file remains. Inspect manually before continuing."
        fi
        die "Expected volume ${OLD_VOLUME} not found. Set COMPOSE_PROJECT_NAME if your project is named differently."
    fi

    # Detect that the volume actually contains a PG12 cluster — if PG_VERSION
    # already says 18 the migration was done; bail out so we don't double-run.
    local pgver
    pgver="$(read_pg_version "${OLD_VOLUME}")"
    if [[ -z "${pgver}" ]]; then
        die "Volume ${OLD_VOLUME} does not look like a Postgres data directory (no PG_VERSION file at pgdata/)."
    fi
    if [[ "${pgver}" != "12" ]]; then
        die "Volume ${OLD_VOLUME} reports PG_VERSION=${pgver}, expected 12. Aborting — this script is only for the 12 → 18 jump."
    fi

    log "OK — found PG12 cluster in volume ${OLD_VOLUME}"
}

step_cold_tar_backup() {
    if [[ "${RESUME_FROM_RESTORE}" == "1" ]]; then
        log "Resume: PG12 data already preserved in ${BACKUP_VOLUME}, skipping cold tarball"
        return
    fi
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
    if [[ "${RESUME_FROM_RESTORE}" == "1" ]]; then
        log "Resume: reusing existing dump ${DUMP_FILE}"
        return
    fi
    if [[ -s "${DUMP_FILE}" ]]; then
        log "Logical dump already exists at ${DUMP_FILE} — skipping"
        return
    fi
    log "Starting temporary PG12 container to take a logical dump"
    # PGDATA must match the compose service (pgdata/ sub-path); otherwise
    # postgres would try to init a fresh cluster at the mountpoint root
    # instead of picking up the existing one.
    docker run -d --rm \
        --name "${TMP_OLD_CTR}" \
        -v "${OLD_VOLUME}:/var/lib/postgresql/data" \
        -e POSTGRES_USER="${POSTGRES_USER}" \
        -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
        -e PGDATA=/var/lib/postgresql/data/pgdata \
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
    #
    # The bootstrap superuser is deliberately NOT ${POSTGRES_USER}. The
    # dump was taken with `pg_dumpall --clean`, which emits `DROP ROLE
    # ${POSTGRES_USER}` early on. Postgres refuses to drop the role the
    # restore session is connected as, so we bootstrap with a throwaway
    # superuser ("migrator") and let the dump recreate ${POSTGRES_USER}
    # itself. When compose brings up the real service, it connects as
    # ${POSTGRES_USER} exactly as before.
    local BOOTSTRAP_USER="migrator"
    docker run -d --rm \
        --name "${TMP_NEW_CTR}" \
        -v "${NEW_VOLUME}:/var/lib/postgresql/data" \
        -v "${DUMP_DIR}:/dumps:ro" \
        -e POSTGRES_USER="${BOOTSTRAP_USER}" \
        -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
        -e PGDATA=/var/lib/postgresql/data/pgdata \
        "${NEW_IMAGE}" >/dev/null

    log "Waiting for PG18 to accept connections"
    for i in $(seq 1 60); do
        if docker exec "${TMP_NEW_CTR}" pg_isready -U "${BOOTSTRAP_USER}" >/dev/null 2>&1; then
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
        psql -v ON_ERROR_STOP=1 -U "${BOOTSTRAP_USER}" -d postgres \
        -f "/dumps/$(basename "${DUMP_FILE}")"

    # PG18 defaults to scram-sha-256 for network auth; PG12 defaulted to md5.
    # pg_dumpall exports the pre-hashed rolpassword verbatim, so the restored
    # roles keep their md5 hashes and pg_hba.conf's `scram-sha-256` rule
    # rejects them at login. Re-hash the two IRIS roles with the plaintext
    # from .env so the running app can connect on first boot.
    log "Re-hashing role passwords as scram-sha-256 (PG18 default)"
    docker exec -i "${TMP_NEW_CTR}" \
        psql -v ON_ERROR_STOP=1 -U "${BOOTSTRAP_USER}" -d postgres <<SQL
SET password_encryption = 'scram-sha-256';
ALTER USER "${POSTGRES_USER}" WITH PASSWORD '${POSTGRES_PASSWORD}';
$( [[ -n "${POSTGRES_ADMIN_USER:-}" && -n "${POSTGRES_ADMIN_PASSWORD:-}" ]] && \
   echo "ALTER USER \"${POSTGRES_ADMIN_USER}\" WITH PASSWORD '${POSTGRES_ADMIN_PASSWORD}';" )
SQL

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
