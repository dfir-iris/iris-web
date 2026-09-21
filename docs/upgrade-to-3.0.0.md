# Upgrading IRIS to v3.0.0-beta

> **Audience:** operators currently running IRIS **v2.4.29** (or any v2.4.x)
> against the bundled `iriswebapp_db` image, which ships PostgreSQL **12**.
> **Target:** v3.0.0-beta.1, which ships PostgreSQL **18** in the same image.

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
- **Update the IRIS source tree** to the v3.0.0-beta.1 tag before running
  the migration — the script lives at
  `scripts/upgrade-db-pg12-to-pg18.sh`.

## 2. What changes

| Component | v2.4.x | v3.0.0-beta.1 |
| --- | --- | --- |
| `iris-backend/docker/db/Dockerfile` base image | `postgres:12-alpine` | `postgres:18-alpine` |
| Meta `.env` — `IRIS_VERSION` (pins all ghcr.io/dfir-iris/iris-{backend,db,nginx,frontend} tags) | `v2.4.20` | `v3.0.0-beta.1` |
| Registry image names | `ghcr.io/dfir-iris/iriswebapp_{app,db,nginx}` | `ghcr.io/dfir-iris/iris-{backend,db,nginx,frontend}` |
| Container names | `iriswebapp_*` | `iris_*` |
| Kubernetes (`iris-backend/deploy/` Helm chart + EKS manifests) | supported, v2 images | **unsupported** — the chart and manifests are still v2-era, see §5 |
| Services in `docker-compose.yml` | 5 (`app`, `worker`, `db`, `rabbitmq`, `nginx`) | 6 — adds `frontend` (SvelteKit SSR) |
| UI stack | jQuery-based, served by `app` | SvelteKit SSR from `frontend`; nginx sends everything to `frontend`, which proxies `/api/v2/*`, `/auth/*` and `/static/*` on to `app` |
| REST API surface reachable from outside | v1 (`/case/…`, `/manage/…`) and `/api/v2/…` | `/api/v2/…` only — see §2.3 |
| PG client auth method | `md5` (PG12 default) | `scram-sha-256` (PG18 default) — the migration script re-hashes existing roles automatically |
| Existing logins | carried over | **all sessions closed** — everyone signs in once after the upgrade, see §2.4 |

The IRIS application schema is unchanged by this jump itself — Alembic
migrations are applied as normal on first boot of the new app container.
Only the underlying PostgreSQL major version changes.

### 2.1 About the new `frontend` service

V3 ships a rewritten UI as a separate SvelteKit SSR service (image
`ghcr.io/dfir-iris/iris-frontend`). It runs on the same host network as
the app and worker containers, listens on port 5173 internally, and
receives *all* inbound HTTP from nginx — including API traffic, which its
SSR proxy forwards to `app`. (The one exception is `/socket.io`, which
nginx sends straight to `app`.) Operators do not
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

### 2.3 The legacy v1 API is no longer reachable

**This is the change most likely to break external automation.** Check it
before you upgrade.

In v2.4.x, scripts could call the v1 REST routes directly — `POST /case/ioc/add`,
`GET /manage/users/list`, `POST /manage/cases/add`, and so on. In
v3.0.0-beta.1 those routes are still *registered* inside the `app`
container, but nothing outside can reach them: nginx hands every request
to the `frontend` service, whose SSR proxy only forwards three prefixes
to `app` — `/api/v2/*`, `/auth/*` and `/static/*`. A v1 path now returns
the frontend's 404 page rather than a JSON API response.

What to do:

- **Audit your integrations before upgrading.** Anything calling a path
  that does not start with `/api/v2/` needs to move. Grep your automation
  for the IRIS hostname and check the paths.
- **Port to `/api/v2/…`.** Most v1 routes have a v2 counterpart —
  `POST /api/v2/cases/{case_id}/iocs`, `GET /api/v2/manage/users`, and so
  on. Browse the full surface at `https://<IRIS_HOSTNAME>/api-docs`, or
  read `iris-backend/source/app/blueprints/rest/openapi.generated.yaml`.
- **A few v1 capabilities have no v2 counterpart yet.** The two worth
  knowing about:
  - *Bulk CSV import* (`POST /case/ioc/upload`, `/case/assets/upload`,
    `/case/timeline/events/csv_upload`). The feature itself is still in
    the UI — v3 parses the CSV in the browser and creates one object per
    row over v2 — but there is no single-call bulk endpoint for scripts.
    Automation that posted a CSV blob has to loop over
    `POST /api/v2/cases/{case_id}/{iocs,assets,events}` instead.
  - *The case task log* (`POST /case/tasklog/add`), which appended a
    free-text entry to a case's activity feed.
    `GET /api/v2/cases/{case_id}/activities` reads the feed, but nothing
    in v2 writes to it.

  If you depend on one of these, please open an issue so it can be
  prioritised before v3.0.0 final.

Nothing in the IRIS UI itself uses v1, so this affects external API
consumers only.

### 2.4 Everyone is signed out once

The upgrade closes every authentication session that is currently open.
Anyone using IRIS when you upgrade is signed out and signs in again; API
clients holding an access or refresh token get `401` until they
re-authenticate against `POST /api/v2/auth/login`.

This is deliberate. Sessions are now tracked server-side so they can be
revoked, and a session opened by an older version does not carry the
state the new authentication path needs — in particular, whether the
second factor was ever actually presented. Rather than assume, the
upgrade asks everyone once.

What to do about it:

- **Pick a maintenance window as if it were a restart.** It is one
  sign-in, not a reset: nobody's password, MFA enrolment or API key
  changes.
- **API keys are unaffected.** Integrations that authenticate with an
  IRIS API key rather than a token keep working across the upgrade.
- **If `enforce_mfa` is on**, users who have not yet enrolled an
  authenticator are sent to the enrolment screen on their next sign-in.
  That was already the intent of the setting; before this release, a
  session that predated the setting being turned on could keep going
  without being challenged.

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

### 3.2 Pull the v3.0.0-beta.1 source

V3 introduces the submodule layout — `iris-web` becomes the meta-repo
with `iris-backend` and `iris-frontend` submodules. When checking out
the tag, update submodules too.

```bash
git fetch --tags
git checkout v3.0.0-beta.1
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

### 3.4 Bring up v3.0.0-beta.1

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

**Kubernetes is not a supported deployment path for v3.0.0-beta.1.**
Docker Compose is the only one. The Helm chart and the EKS manifests
under `iris-backend/deploy/` are v2-era artefacts that were never
updated for v3 — there are no v3.0.0-beta.1 manifests to apply, and
applying the ones in the tree gets you a v2 stack or a broken one.
Kubernetes support is intended to return before v3.0.0 stable; no date
is promised.

What is actually wrong, so you can verify it yourself:

| Artefact | State |
| --- | --- |
| `deploy/eks_manifest/app/deployment.yml:22`, `deploy/eks_manifest/worker/deployment.yml:22` | `image: iriswebapp_app:v2.2.2` — v2 image name, v2 tag. V3 publishes `ghcr.io/dfir-iris/iris-backend`; no `iriswebapp_app:v3.0.0-beta.1` exists to bump to. |
| `deploy/eks_manifest/psql/deployment.yml:22` | `image: iriswebapp_db:v2.2.2` — PostgreSQL 12, not 18 |
| `deploy/kubernetes/charts/templates/` | `iris_app`, `iris_worker`, `postgres`, `rabbitmq`, `ingress` — **no frontend template**. V3's UI is a separate SvelteKit service (§2.1) that the chart cannot run, and the ingress routes straight to the Flask app on port 8000. A Helm deploy therefore serves no v3 UI. |
| `deploy/kubernetes/charts/values.yaml`, `Chart.yaml` | still `iriswebapp-app` / `iriswebapp-worker` naming; `appVersion: "2.4.5"` |
| `iris-backend/.github/workflows/chart-releaser.yml` | triggers on `branches: [main]`, and `iris-backend` has no `main` branch — the chart has never been published to a Helm repository |

### 5.1 What to do for the beta

Pick one:

- **Stay on v2.4.x.** Your current Kubernetes deployment keeps working
  on PG12. Do nothing. Wait for Kubernetes support to land before
  v3.0.0 stable.
- **Move to Docker Compose.** Follow §3 for the target stack, and §5.2
  below to get your data from the PVC into the compose volume.

Do not try to hand-roll v3 manifests off the chart for a production
instance during the beta — the missing frontend service, the nginx
routing split between `/api/*` and the SvelteKit app (§2.1), and the
new required env vars (§3.2b) are not modelled anywhere in
`deploy/`.

### 5.2 Moving a Kubernetes deployment to Docker Compose

The PG12 → PG18 jump still applies: a PG18 server will not start
against a PG12 data directory, so the move is a dump and restore.
`scripts/upgrade-db-pg12-to-pg18.sh` only knows about Docker volumes,
so do it by hand.

1. Scale the app and worker Deployments to 0. Leave PG12 running.
2. Snapshot the PVC (cloud-provider feature). Keep the whole cluster in
   place until the compose stack is verified — that is your rollback.
3. Dump roles and data out to the host:
   ```bash
   kubectl exec <pg12-pod> -- \
       pg_dumpall -U "$POSTGRES_USER" --clean --if-exists > iris_pg12_dump.sql
   ```
4. Prepare the compose stack per §3.2 through §3.2c on the target host,
   then bring up the database alone:
   ```bash
   docker compose up -d db
   ```
5. Replay the dump into the fresh PG18 cluster:
   ```bash
   docker compose exec -T db \
       psql -v ON_ERROR_STOP=1 -U "$POSTGRES_ADMIN_USER" -d postgres < iris_pg12_dump.sql
   ```
6. Re-hash the role passwords. `pg_dumpall` exports the stored md5
   hashes verbatim and PG18's `pg_hba.conf` expects `scram-sha-256`, so
   the app will fail to authenticate until you do:
   ```bash
   docker compose exec db psql -U "$POSTGRES_ADMIN_USER" -d postgres \
       -c "SET password_encryption = 'scram-sha-256';
           ALTER USER \"$POSTGRES_USER\" WITH PASSWORD '$POSTGRES_PASSWORD';
           ALTER USER \"$POSTGRES_ADMIN_USER\" WITH PASSWORD '$POSTGRES_ADMIN_PASSWORD';"
   ```
   Repeat for any role you provisioned yourself (see §6).
7. `docker compose up -d`, then verify per §3.5. Only then tear down
   the Kubernetes deployment.

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
only covers the v2.4.x → v3.0.0-beta.1 jump. If you are on something
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
