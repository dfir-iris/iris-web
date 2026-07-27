# Error reporting (Sentry / GlitchTip)

> **Audience:** operators of an IRIS install (community or commercial,
> on-prem or hosted) who want unhandled exceptions and user bug
> reports forwarded to a Sentry-compatible collector.

IRIS ships with a built-in error reporter that speaks the Sentry
ingest protocol. It targets **any Sentry-compatible endpoint** —
Sentry itself, GlitchTip, or any collector implementing the same
wire. Reporting is **off by default on every install** and requires
an admin (server-administrator permission) to enable it.

---

## What gets captured

When enabled, the reporter forwards:

- **Unhandled server exceptions** — any exception that reaches the
  Flask error handler, plus everything the existing 30+
  `app.logger.exception(...)` call sites already log. The
  `sentry_sdk` LoggingIntegration promotes them to Sentry events
  automatically; existing call sites are not changed.
- **Unhandled browser errors** — every uncaught exception, promise
  rejection, and SvelteKit `handleError` event.
- **Manual bug reports** — the "Report an issue" button in the top
  bar. Submits via `Sentry.captureFeedback` when the browser SDK is
  initialised, otherwise falls back to `POST /api/v2/bug-reports`
  which logs to `app.logger.warning` and drops an activity-log row.

Each event carries a `request_id` tag that matches the
`X-Request-Id` response header the backend echoes on every API
call. Front-end and back-end events for the same request can be
paired via that id.

## What is redacted before send

The reporter is designed for DFIR case content, which must never
cross the network in a crash-report payload. Before every event
leaves the server, a redactor:

- Drops **request cookies** entirely.
- Redacts values of **request headers** matching
  `authorization|cookie|proxy-authorization|x-.*-token|x-.*-key|x-api-key`.
- Redacts values of **request-body / query-string / stack-frame
  local** keys matching
  `secret|token|password|passwd|key|credential|api[_-]?key|dsn|cookie|session`.
- Redacts values of any local named
  `ioc|evidence|malware|indicator|payload|hash|artifact` — a
  belt-and-braces catch for DFIR-shaped variables.
- Redacts **entire stack-frame locals** for known-sensitive modules
  (`iris_engine/mail/secrets.py`, `iris_engine/access_control/`,
  `iris_engine/mail/config.py`).
- Sets `send_default_pii=false`, `traces_sample_rate=0`,
  `max_breadcrumbs=30`.

A **strict mode** (`REPORTER_STRICT_FRAME_VARS=1` in the process
environment) drops **all** stack-frame locals wholesale, regardless
of name. Recommended for installs shipping reports off-box.

The browser SDK runs a symmetric redactor before every event and
drops `fetch` breadcrumbs (their URL may carry an IOC value).

## Enabling on an on-prem install

1. **Stand up a collector.** For a self-hosted setup, run GlitchTip
   via its official Docker Compose file. Any Sentry-compatible
   collector works. You need two **project DSNs** — one for the
   server, one for the browser. Their public keys are safe to hand
   to browsers; the private half (if present) stays with the
   collector.

2. **Sign in as a server administrator** and open **Settings →
   Server**. Scroll to the **Error reporting** section.

3. **Fill in** the two DSNs plus the environment tag (`prod` /
   `staging` / your install nickname) and adjust the sample rate if
   needed (default 1.0 = every event). Leave "Attach user identity
   to events" off unless you're comfortable with usernames landing
   in the collector.

4. **Flip the toggle.** The server reloads its SDK in-place — no
   restart needed. Trigger any error to confirm events land in the
   collector; the response's `X-Request-Id` header matches the
   `request_id` tag on the event.

5. **Reload any open browser tabs.** The SPA reads the DSN once at
   boot from `/api/v2/runtime-config`; a page reload picks up the
   new value.

The **backend DSN is stored encrypted at rest** (Fernet, same
mechanism as the mail SMTP password). The **frontend DSN is stored
in plaintext** on purpose — DSNs are ingest tokens, not secrets,
and the browser has to read it to init the SDK. Access to the
DSN in either the API or the settings page requires the
`server_administrator` permission.

## Disabling

Toggle "Enable error reporting" off in the same settings section.
The server swaps to a null Sentry client (no captures) immediately;
the browser stops emitting events on next page reload. Both DSNs
stay in the DB so a later re-enable doesn't require re-entering
them — clear the fields explicitly (blank string) if you want to
purge them.

## The "Report an issue" button

The button in the top bar is **always visible**, even when
reporting is off. Behaviour:

- **Reporting on:** submits via `Sentry.captureFeedback` with an
  auto-synthesised event id. Attaches URL, user-agent, and the last
  `X-Request-Id`.
- **Reporting off:** submits to `POST /api/v2/bug-reports`. The
  backend logs the report as an `app.logger.warning` line and
  writes a `Bug report filed: <title>` activity-log row. Rate
  limited to 5 submissions/min/user.

No screenshot is attached in v1 on either path — deferred.

## Configuration reference

The reporter reads the following fields on `ServerSettings`
(edited via the Server Settings page, or directly via
`PUT /api/v2/manage/server/settings`):

| Field | Type | Default |
|---|---|---|
| `error_reporting_enabled` | boolean | `false` |
| `error_reporting_backend_dsn` | string (Fernet-encrypted) | null |
| `error_reporting_frontend_dsn` | string | null |
| `error_reporting_environment` | string(64) | null |
| `error_reporting_sample_rate` | numeric(3,2) | `1.00` |
| `error_reporting_include_user` | boolean | `false` |

Process-environment knobs:

| Variable | Purpose | Default |
|---|---|---|
| `REPORTER_STRICT_FRAME_VARS` | Drop **all** stack-frame locals, regardless of key name. Recommended for off-box collectors. | unset (regex-based redaction only) |

## Runbook: rotating a DSN

1. In the collector, revoke the old key and mint a new one for the
   same project.
2. Paste the new DSN into the Server Settings page.
3. Save. No restart required; the server rebuilds the SDK client
   on-save and the SPA picks up the new frontend DSN on next
   reload.

## Runbook: pairing an error report to a support ticket

Every ingested event carries a `request_id` tag. The **same id**
is echoed on the API response's `X-Request-Id` header, printed in
the manual bug-report dialog under "Diagnostics", and included in
the JSON error envelope any 500 response returns to a JSON caller.
Ask the customer for the id (or read the header from a captured
response) and search the collector by tag `request_id:<value>`.
