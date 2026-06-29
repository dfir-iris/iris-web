# Upgrading IRIS to v3.0.0-beta

> **Audience:** operators currently running IRIS **v2.4.29** (or any v2.4.x)
> against the bundled `iriswebapp_db` image, which ships PostgreSQL **12**.
> **Target:** v3.0.0-beta, which ships PostgreSQL **18** in the same image.

This release upgrades the bundled database from PostgreSQL 12 to PostgreSQL
18. A PG18 server **cannot read a PG12 data directory** — simply pulling the
new image and restarting will fail with a `database files are incompatible
with server` error. The data must be migrated.

This document and the accompanying script perform a **logical
dump-and-restore** migration. No data is destroyed by the procedure: the
original PG12 volume is preserved under a new name, and a cold tarball is
written to disk before any mutation. You can roll back to v2.4.29 at any
point until you choose to reclaim the backup.

---

## 1. Before you start

- **Schedule a maintenance window.** IRIS must be stopped for the duration
  of the migration. Dump/restore time is roughly proportional to database
  size; on a typical case-management instance budget 1–5 minutes per GB of
  `db_data`.
- **Free disk space.** You will temporarily need free disk equal to roughly
  **3×** the size of the current `db_data` volume (raw tarball + SQL dump +
  the freshly restored PG18 cluster). Check first:
  ```bash
  docker system df -v | grep db_data
  df -h .
  ```
- **Confirm your `.env`** still has the original `POSTGRES_USER` and
  `POSTGRES_PASSWORD`. The migration script reads them to authenticate
  against both the PG12 dump and the PG18 restore.
- **Update the IRIS source tree** to the v3.0.0-beta tag before running
  the migration — the script lives at
  `upgrades/upgrade_db_pg12_to_pg18.sh`.

## 2. What changes

| Component | v2.4.x | v3.0.0-beta |
| --- | --- | --- |
| `docker/db/Dockerfile` base image | `postgres:12-alpine` | `postgres:18-alpine` |
| Default `DB_IMAGE_TAG` | `v2.4.20` | `v3.0.0-beta` |
| Default `APP_IMAGE_TAG` | `v2.4.20` | `v3.0.0-beta` |
| Default `NGINX_IMAGE_TAG` | `v2.4.20` | `v3.0.0-beta` |
| `deploy/eks_manifest/psql/deployment.yml` image tag | `v2.2.2` | `v3.0.0-beta` |

The IRIS application schema is unchanged by this jump itself — Alembic
migrations are applied as normal on first boot of the new app container.
Only the underlying PostgreSQL major version changes.

## 3. Migration procedure (docker-compose deployments)

The steps below correspond to the automation in
`upgrades/upgrade_db_pg12_to_pg18.sh`. Run the script for the happy path;
the prose here is to help you understand and recover if anything goes
sideways.

### 3.1 Stop the stack

```bash
cd /path/to/iris-web
docker compose down
```

Do **not** pass `-v` — that would delete the very volume we're about to
migrate.

### 3.2 Pull the v3.0.0-beta source

```bash
git fetch --tags
git checkout v3.0.0-beta
```

At this point `docker-compose.yml` references the new PG18-based DB image,
but your `db_data` volume still holds a PG12 cluster.

### 3.3 Run the migration script

```bash
./upgrades/upgrade_db_pg12_to_pg18.sh
```

The script:

1. **Pre-flight checks** — confirms Docker is present, the `iriswebapp_db`
   container is stopped, and the existing volume actually contains a PG12
   cluster (reads `PG_VERSION`). Refuses to run otherwise.
2. **Cold tarball backup** — gzipped tar of the entire volume goes to
   `upgrades/backups/iris_pg12_volume_<timestamp>.tar.gz`. This is your
   nuclear-option rollback artifact.
3. **Logical dump** — spins up a throwaway `postgres:12-alpine` container
   bound to the existing volume read-write, runs `pg_dumpall --clean
   --if-exists`, writes
   `upgrades/backups/iris_pg12_dump_<timestamp>.sql`, then stops.
4. **Volume swap** — copies the PG12 volume to a new named volume
   `<project>_db_data_pg12_backup` and removes the original. The backup
   volume is **kept**, not deleted, until you choose to reclaim it.
5. **Restore** — creates a fresh `<project>_db_data` volume, boots a
   throwaway `postgres:18-alpine` against it, replays the dump with
   `psql -v ON_ERROR_STOP=1`, then stops.

The script is idempotent: each step detects prior completion and skips.
If it dies halfway through you can simply rerun it.

### 3.4 Bring up v3.0.0-beta

```bash
docker compose up -d
```

The `iriswebapp_db` container will now run PostgreSQL 18 against the
restored data. The `app` container applies any Alembic migrations on
first boot — watch the logs:

```bash
docker compose logs -f app
```

### 3.5 Verify

- Log in to the UI and confirm cases, IOCs, users, and customizations are
  present.
- Check the new server version:
  ```bash
  docker compose exec db psql -U "$POSTGRES_USER" -d iris_db -c 'SELECT version();'
  ```
  Should report PostgreSQL **18.x**.
- Confirm the `pgcrypto` extension is still present:
  ```bash
  docker compose exec db psql -U "$POSTGRES_USER" -d iris_db \
      -c "SELECT extname, extversion FROM pg_extension WHERE extname='pgcrypto';"
  ```

### 3.6 Reclaim space (only after verification)

Once you are confident the new stack is healthy, drop the preserved
PG12 volume and the on-disk backup artefacts:

```bash
docker volume rm <project>_db_data_pg12_backup
rm upgrades/backups/iris_pg12_*.tar.gz upgrades/backups/iris_pg12_*.sql
```

Do not do this on the same day as the migration. Wait until the next
business cycle so any latent issue surfaces while you still have a
trivial rollback path.

## 4. Rolling back

You can roll back at three different points:

### 4.1 Before reclaiming the backup volume — fastest

```bash
docker compose down
docker volume rm <project>_db_data                          # drop the PG18 cluster
docker volume create <project>_db_data                      # empty target
docker run --rm \
    -v <project>_db_data_pg12_backup:/from:ro \
    -v <project>_db_data:/to \
    alpine:3.20 sh -c 'cd /from && cp -a . /to/'
git checkout v2.4.29
docker compose up -d
```

### 4.2 Before reclaiming the cold tarball — slower but identical outcome

```bash
docker compose down
docker volume rm <project>_db_data
docker volume create <project>_db_data
docker run --rm \
    -v <project>_db_data:/to \
    -v "$(pwd)/upgrades/backups:/backup:ro" \
    alpine:3.20 sh -c 'cd /to && tar xzf /backup/iris_pg12_volume_<timestamp>.tar.gz'
git checkout v2.4.29
docker compose up -d
```

### 4.3 Logical-only rollback

If, much later, you only have the `.sql` dump available, re-deploy
v2.4.29, let it initialise an empty cluster, drop the empty `iris_db`,
then `psql -f iris_pg12_dump_<timestamp>.sql`.

## 5. Kubernetes deployments

The bundled Helm chart and EKS manifest both reference the
`iriswebapp_db` image. The same major-version jump applies — a PG18 pod
will refuse to start against a PG12 `PersistentVolumeClaim`.

We **do not** ship an automated migration for Kubernetes in this
release. Recommended approach:

1. Scale the IRIS app/worker deployments to 0.
2. Exec into the running PG12 pod and `pg_dumpall` to a file on the PVC
   (or stream out via `kubectl exec ... > dump.sql`).
3. Take a volume snapshot of the PVC (cloud-provider feature) as a
   belt-and-braces backup.
4. Delete the PG12 StatefulSet/Deployment and its PVC.
5. Apply the v3.0.0-beta manifests so PG18 initialises a fresh PVC.
6. `kubectl cp` the dump into the new PG18 pod and `psql -v
   ON_ERROR_STOP=1 -f dump.sql`.
7. Scale the app/worker back up.

If you need a scripted version, open an issue — we will prioritise it
based on demand.

## 6. FAQ

**Why not `pg_upgrade`?** `pg_upgrade` is faster but requires both
PG12 *and* PG18 binaries side-by-side in a single container, plus
matching `--bindir` layouts. Bundling both inflates the image and adds
a brittle code path. Logical dump-and-restore is a few minutes slower
on typical IRIS datasets and is far easier to reason about.

**Will the dump preserve roles and passwords?** Yes —
`pg_dumpall` (not `pg_dump`) is used precisely so that the
`POSTGRES_USER` and `POSTGRES_ADMIN_USER` roles, their passwords, and
ownership are restored exactly.

**My `db_data` volume is huge — can I stream instead of writing the
`.sql` file to disk?** Possible but not implemented in the bundled
script, because writing the dump to disk is what makes the procedure
restartable. If disk is a hard constraint, contact us before
migrating.

**Can I jump straight from a much older IRIS version?** This document
only covers the v2.4.x → v3.0.0-beta jump. If you are on something
older, upgrade to v2.4.29 first using
[`upgrades/upgrade_to_2.0.0.py`](upgrade_to_2.0.0.py) and the regular
release notes, then come back here.
