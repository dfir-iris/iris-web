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
- **Plan for `.env` changes.** V3 introduces several new required
  variables and expects a self-signed TLS cert in a specific path — see
  §3.2b below. Do not skip that step, or the stack will fail to boot
  even after the DB migration succeeds.
- **Update the IRIS source tree** to the v3.0.0-beta tag before running
  the migration — the script lives at
  `scripts/upgrade-db-pg12-to-pg18.sh`.

## 2. What changes

| Component | v2.4.x | v3.0.0-beta |
| --- | --- | --- |
| `iris-backend/docker/db/Dockerfile` base image | `postgres:12-alpine` | `postgres:18-alpine` |
| Meta `.env` — `IRIS_VERSION` (pins all ghcr.io/dfir-iris/iris-{backend,db,nginx,frontend} tags) | `v2.4.20` | `v3.0.0-beta` |
| Registry image names | `ghcr.io/dfir-iris/iriswebapp_{app,db,nginx}` | `ghcr.io/dfir-iris/iris-{backend,db,nginx,frontend}` |
| Container names | `iriswebapp_*` | `iris_*` |
| `iris-backend/deploy/eks_manifest/psql/deployment.yml` image tag | `v2.2.2` | `v3.0.0-beta` |
| Services in `docker-compose.yml` | 5 (`app`, `worker`, `db`, `rabbitmq`, `nginx`) | 6 — adds `frontend` (SvelteKit SSR) |
| UI stack | jQuery-based, served by `app` | SvelteKit SSR from `frontend`; nginx proxies `/api/*` to `app`, everything else to `frontend` |
| PG client auth method | `md5` (PG12 default) | `scram-sha-256` (PG18 default) — the migration script re-hashes existing roles automatically |

The IRIS application schema is unchanged by this jump itself — Alembic
migrations are applied as normal on first boot of the new app container.
Only the underlying PostgreSQL major version changes.

### 2.1 About the new `frontend` service

V3 ships a rewritten UI as a separate SvelteKit SSR service (image
`ghcr.io/dfir-iris/iris-frontend`). It runs on the same host network as
the app and worker containers, listens on port 5173 internally, and is
proxied by nginx for everything that isn't `/api/*`. Operators do not
interact with it directly; the compose file wires it up, sets sensible
defaults for its env vars (`PUBLIC_EXTERNAL_API_URL`, `ORIGIN`,
`BODY_SIZE_LIMIT`), and its healthcheck gates nginx startup along
with the app healthcheck.

### 2.2 Build-from-source deployments

V3 introduces the submodule layout for operators who build their own
images. If you were building v2 from source, the equivalent v3
workflow is:

```bash
git clone --recursive https://github.com/dfir-iris/iris-web.git
cd iris-web
git checkout v3.0.0-beta.1
./scripts/dev-up.sh
```

`scripts/dev-up.sh` composes `docker-compose.yml` + `docker-compose.build.yml`
(which points build contexts at the `iris-backend/` and `iris-frontend/`
submodules) and passes `--build` to compose. Pull-only operators do not
need to initialise submodules.

## 3. Migration procedure (docker-compose deployments)

The steps below correspond to the automation in
`scripts/upgrade-db-pg12-to-pg18.sh`. Run the script for the happy path;
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

V3 introduces the submodule layout — `iris-web` becomes the meta-repo
with `iris-backend` and `iris-frontend` submodules. When checking out
the tag, update submodules too.

```bash
git fetch --tags
git checkout v3.0.0-beta
git submodule update --init --recursive
```

At this point `docker-compose.yml` references the new PG18-based DB image,
but your `db_data` volume still holds a PG12 cluster.

### 3.2b Migrate your `.env`

V3 introduces new env vars, renames a few, and drops the legacy
`.env.model` file in favour of `.env.example` at the meta root. Your
v2 `.env` will not boot v3 as-is.

Diff your existing `.env` against the new template:

```bash
diff -u .env .env.example | less   # visual diff — merge new keys manually
```

The variables you **must** add or verify (with brief purpose):

| Variable | v2 default | v3 default | Required for |
| --- | --- | --- | --- |
| `IRIS_VERSION` | *not set* | `v3.0.0-beta.1` | pins all four service image tags together — do not omit |
| `IRIS_HOSTNAME` | *not set* | `localhost` | derives `SERVER_NAME`, `PUBLIC_EXTERNAL_API_URL`, `ORIGIN` (SvelteKit CSRF gate) when they are empty |
| `POSTGRES_SERVER` | *not set* | `db` | app + worker DB connection |
| `POSTGRES_PORT` | *not set* | `5432` | app + worker DB connection |
| `POSTGRES_ADMIN_USER` | *not set* | `postgres` | schema/role management on first boot |
| `POSTGRES_ADMIN_PASSWORD` | *not set* | *unset — must set* | schema/role management |
| `IRIS_SECURITY_PASSWORD_SALT` | *sometimes set* | *unset — must set* | Flask-Security session hashing |
| `KEY_FILENAME` / `CERT_FILENAME` | *not set* | `iris_dev_key.pem` / `iris_dev_cert.pem` | nginx TLS material lookup under `certificates/web_certificates/` |
| `IRIS_CERT_RELOAD_INTERVAL` | n/a | `60` | nginx polls the cert mtime; set `0` to disable |
| `INTERFACE_HTTPS_PORT` | `443` | `443` | host-side HTTPS port |
| `PUBLIC_EXTERNAL_API_URL` | n/a | derived from `IRIS_HOSTNAME` | SvelteKit SSR — external URL the browser will use |
| `ORIGIN` | n/a | derived from `IRIS_HOSTNAME` | SvelteKit CSRF gate — must match the URL the browser uses |
| `BODY_SIZE_LIMIT` | n/a | `Infinity` | SvelteKit body cap — per-endpoint limits live in nginx |
| `LOG_LEVEL` | n/a | `info` | app + worker log verbosity |

Vars that **behaved differently** in v2 and may need tuning:

- `SERVER_NAME` — nginx now strips scheme/path so you can drop a full URL
  in `.env` (e.g. `https://iris.lab`) without breaking the `server_name`
  directive. Bare hostnames still work.

### 3.2c Provide a TLS cert

V3's nginx expects
`certificates/web_certificates/iris_dev_cert.pem` and
`certificates/web_certificates/iris_dev_key.pem` to exist before the
stack comes up (or whatever `CERT_FILENAME` / `KEY_FILENAME` in `.env`
point at). If you were serving TLS from v2's nginx, **the file names
and expected mount path have not changed** — but the directory may not
yet exist in a fresh v3 checkout, since the cert files are now
`.gitignore`d.

- **Reusing v2 certs:** copy them into
  `certificates/web_certificates/` with the filenames named above (or
  update `.env`).
- **Generating a fresh self-signed pair (dev only):**
  ```bash
  mkdir -p certificates/web_certificates
  openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
      -keyout certificates/web_certificates/iris_dev_key.pem \
      -out certificates/web_certificates/iris_dev_cert.pem \
      -subj "/CN=iris.local" \
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
  chmod 600 certificates/web_certificates/iris_dev_key.pem
  ```
  Build-from-source operators can skip this step — `scripts/dev-up.sh`
  mints the pair automatically on first run.
- **Let's Encrypt / certbot:** unset both `CERT_FILENAME` and
  `KEY_FILENAME` in `.env`. The nginx entrypoint autodetects
  `fullchain.pem` + `privkey.pem` if they exist under
  `certificates/web_certificates/`. See
  `iris-backend/scripts/certbot-deploy-hook.sh` for the renewal
  wiring.

### 3.3 Run the migration script

```bash
./scripts/upgrade-db-pg12-to-pg18.sh
```

The script:

1. **Pre-flight checks** — confirms Docker is present, the IRIS db
   container (`iriswebapp_db` on v2, renamed to `iris_db` on V3) is
   stopped, and the existing volume actually contains a PG12 cluster
   (reads `PG_VERSION`). Refuses to run otherwise.
2. **Cold tarball backup** — gzipped tar of the entire volume goes to
   `backups/iris_pg12_volume_<timestamp>.tar.gz`. This is your
   nuclear-option rollback artifact.
3. **Logical dump** — spins up a throwaway `postgres:12-alpine` container
   bound to the existing volume read-write, runs `pg_dumpall --clean
   --if-exists`, writes
   `backups/iris_pg12_dump_<timestamp>.sql`, then stops.
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

The `iris_db` container (renamed from `iriswebapp_db` in V3) will now
run PostgreSQL 18 against the restored data. The `app` container
applies any Alembic migrations on first boot — watch the logs:

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
rm backups/iris_pg12_*.tar.gz backups/iris_pg12_*.sql
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
    -v "$(pwd)/backups:/backup:ro" \
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
[`iris-backend/upgrades/upgrade_to_2.0.0.py`](../iris-backend/upgrades/upgrade_to_2.0.0.py)
and the regular release notes, then come back here.

**Why is my role's password no longer accepted after the migration?**
PG18 defaults to `scram-sha-256` client authentication, where PG12
used `md5`. The migration script silently re-hashes the `POSTGRES_USER`
and `POSTGRES_ADMIN_USER` roles' stored passwords to the new scheme
using the values in your `.env`, so the app + worker containers
authenticate normally. If you provisioned additional roles outside
the app (custom read-only reporting user, etc.), you must re-hash them
manually:
```bash
docker compose exec db psql -U "$POSTGRES_ADMIN_USER" -d iris_db \
    -c "ALTER USER myuser WITH PASSWORD 'their-existing-password';"
```
The `ALTER USER ... WITH PASSWORD` re-encodes using PG18's active
`password_encryption` setting, which is `scram-sha-256`.

**The migration script failed halfway through — do I need to start
over?** No. The script is restartable: each step detects prior
completion and skips it. Rerun the same command and it will pick up
from where it left off. If step 5 (restore) failed and you want to
force a full replay of just the restore against the fresh PG18 volume,
export `RESUME_FROM_RESTORE=1` before rerunning.
