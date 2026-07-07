#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""SocketIO namespace `/collab` — real-time collaborative editing.

Transport layer for a server-authoritative Yjs setup:

  * Receive `join {doc}` → resolve ACL → `ensure_snapshot` (seeds Y.Doc
    from source column on first open) → `join_room(doc)` → emit
    `sync-init` with the authoritative `y_state` bytes.
  * Receive `sync {doc, update}` → ACL re-check → `apply_wire_update`
    merges into the server's authoritative Y.Doc, persists → rebroadcast
    the update to peers (they apply it into their local Y.Docs; CRDT
    convergence guarantees identical state).
  * Receive `awareness {doc, update, client_id}` → rebroadcast +
    server-attested `awareness-identity` companion for spoof-proof
    cursor labels.
  * Receive `leave {doc}` (or disconnect) → `leave_room` → if that
    was the last client on the doc, flush the Y.Doc back to the source
    column as markdown.

`content_md` is NEVER on the wire in this version — the client only
sends Yjs updates, and the server owns the markdown rendering.
Everything else — doc-name schema, ACL rules, snapshot storage —
lives in `app.business.collab`.
"""

import base64
import logging

from flask import g, request
from flask_socketio import emit
from flask_socketio import join_room
from flask_socketio import leave_room

from app import socket_io
from app.blueprints.access_controls import is_user_authenticated
from app.blueprints.iris_user import iris_current_user
from app.business.auth import validate_auth_token
from app.business.collab import DocResolutionError
from app.business.collab import apply_wire_update
from app.business.collab import ensure_snapshot
from app.business.collab import flush_to_source
from app.business.collab import resolve_doc


logger = logging.getLogger(__name__)


NAMESPACE = '/collab'


# --- Resource caps --------------------------------------------------------
# The `/collab` transport is authenticated but the payloads are opaque
# blobs — we can't inspect a Yjs update to decide whether it's "safe",
# so we cap size + count instead. All limits are per-message except
# `_MAX_DOCS_PER_SID` which is per-connection.

# Base64-encoded Yjs update. A typical single-keystroke update is
# under 200 bytes; a bulk paste of a large document might reach a few
# hundred KB. 1 MiB is a comfortable ceiling that covers legitimate
# use and hard-stops anything trying to burn RAM.
_MAX_UPDATE_B64_LEN = 1 * 1024 * 1024

# Awareness updates are cursor + user identity — always small.
_MAX_AWARENESS_B64_LEN = 64 * 1024

# Cap concurrent docs per connection so a single misbehaving client
# can't burn resolver/DB cycles by joining thousands of doc-names.
_MAX_DOCS_PER_SID = 32

# Track which docs each sid has joined so we can drive per-doc leave
# on disconnect. flask-socketio doesn't hand us the room list on a
# raw disconnect event, so we mirror it here. Doubles as the source
# of truth for the sender-membership check that gates every relay.
_sid_docs: dict[str, set[str]] = {}

# `g.auth_user` populated on the connect handler doesn't survive to
# subsequent events (each event runs in its own request context). We
# mirror the authenticated user id per-sid so downstream handlers can
# resolve identity without redoing the JWT validation on every message.
_sid_user_ids: dict[str, int] = {}

# Per-doc mapping from Yjs `client_id` → authenticated `user_id`, so we
# only emit `awareness-identity` when a client_id is new to the room (or
# its identity has changed). Without this we broadcast identity on every
# keystroke of every peer, which triggers the client to overwrite the
# local awareness state and re-render every remote cursor — that's what
# the user reported as "text blinking because it comes and goes."
_doc_client_identities: dict[str, dict[int, int]] = {}


def _current_user_id():
    """Return the authenticated user id for the socket event in flight.

    Checks the session/g-based `iris_current_user` first (works when the
    session cookie is present, e.g. classical login flow). Falls back
    to our per-sid mirror populated on connect from the socket.io
    `auth` payload — that's the path used by the SPA behind an SSO
    proxy where the WS upgrade strips the `Authorization` header.
    """
    user = iris_current_user._get_current_object()  # type: ignore[attr-defined]
    if user is not None:
        uid = getattr(user, 'id', None)
        if uid:
            return uid
    return _sid_user_ids.get(getattr(request, 'sid', None))


def _current_user_name():
    user = iris_current_user._get_current_object()  # type: ignore[attr-defined]
    if user is not None:
        # `user.user` is the login handle used in existing socket handlers;
        # keep parity so awareness user labels look the same everywhere.
        name = getattr(user, 'user', None) or getattr(user, 'name', None)
        if name:
            return name
    # Fallback path (auth-payload only, no session context): look up
    # the user by id. Cache miss is fine — the resolver still works
    # with just the id, we lose the pretty name in awareness relays
    # for one lookup.
    uid = _sid_user_ids.get(getattr(request, 'sid', None))
    if not uid:
        return None
    from app.datamgmt.manage.manage_users_db import get_user
    user_row = get_user(uid)
    return getattr(user_row, 'user', None) if user_row else None


@socket_io.on('connect', namespace=NAMESPACE)
def on_connect(auth):
    """Reject unauthenticated sessions at connect time.

    Auth resolution order:
      1. Standard `is_user_authenticated(request)` — session cookie or
         `Authorization` header if the deployment happens to preserve
         it (rare through nginx WS proxies, but supported).
      2. Fallback: token supplied via socket.io's `auth` handshake
         payload. Browsers won't attach custom headers to WS handshakes
         so the SPA sends the Flask JWT via `io(url, {auth: {token}})`;
         Flask-SocketIO passes it here as the `auth` argument.

    On success we store the user id in `_sid_user_ids` so downstream
    events (which run in fresh request contexts and don't inherit
    `g.auth_user`) can still identify the caller via
    `_current_user_id()`.
    """
    user_id = None

    if is_user_authenticated(request):
        # Header/session path — `iris_current_user` is populated for
        # this request context. Grab the id off it directly.
        user_obj = iris_current_user._get_current_object()  # type: ignore[attr-defined]
        user_id = getattr(user_obj, 'id', None) if user_obj else None

    if user_id is None and isinstance(auth, dict):
        token = auth.get('token')
        if isinstance(token, str) and token:
            user_data = validate_auth_token(token)
            if user_data and not (
                user_data.get('mfa_required') and not user_data.get('mfa_verified')
            ):
                g.auth_user = user_data
                g.auth_token_user_id = user_data['user_id']
                user_id = user_data['user_id']

    if user_id is None:
        return False

    _sid_docs[request.sid] = set()
    _sid_user_ids[request.sid] = user_id
    return True


@socket_io.on('disconnect', namespace=NAMESPACE)
def on_disconnect():
    """Clean up rooms this sid was in, and flush any doc that lost its
    last client."""
    _sid_user_ids.pop(request.sid, None)
    docs = _sid_docs.pop(request.sid, set())
    for doc_name in docs:
        leave_room(doc_name)
        _maybe_flush_if_empty(doc_name)


def _room_is_empty(doc_name):
    """True if no sids are currently in the doc's room.

    flask-socketio exposes `.rooms` on the underlying server; we walk
    it defensively because the API surface has changed between minor
    versions.
    """
    try:
        server = socket_io.server
        # `rooms` on a Server returns a dict keyed by namespace when
        # called with no args; we want the count for our namespace.
        room_members = server.manager.get_participants(NAMESPACE, doc_name)
        # `get_participants` is an iterator of (sid, eio_sid) pairs.
        for _ in room_members:
            return False
        return True
    except Exception:
        # If we can't tell, err on the side of NOT flushing here — the
        # doc will still flush when another client eventually joins
        # and leaves cleanly. Flushing too often is harmless (idempotent
        # writes) but flushing incorrectly on a live doc could produce
        # a spurious activity-log entry.
        logger.debug('collab: could not enumerate room %s', doc_name)
        return False


def _maybe_flush_if_empty(doc_name):
    """If the doc has no more connected clients, write its markdown
    back to the source column and fire the audit log entry."""
    if not _room_is_empty(doc_name):
        return
    try:
        flush_to_source(doc_name)
    except Exception:
        # Never let a flush failure surface as a socket-level error —
        # the client isn't waiting on this. Log and move on.
        logger.exception('collab: flush failed for %s', doc_name)
    # Drop the per-doc identity cache so the next fresh open re-broadcasts
    # identities cleanly. Also stops the map from growing forever across
    # doc lifetimes.
    _doc_client_identities.pop(doc_name, None)


@socket_io.on('join', namespace=NAMESPACE)
def on_join(data):
    """Client asks to join a doc's room.

    Payload: `{doc: '<kind>:<id>'}`. On success we join the room and
    immediately emit `sync-init` back to the caller only, carrying the
    authoritative `y_state` bytes (base64) and the caller's write permission.

    Emits `permission-denied` if the caller lacks read access, or
    `resolution-error` if the doc-name shape is wrong / the target
    doesn't exist.
    """
    user_id = _current_user_id()
    if not user_id or not isinstance(data, dict):
        return
    doc_name = data.get('doc')
    if not isinstance(doc_name, str):
        emit('resolution-error', {'reason': 'doc must be a string'})
        return

    # Cap the number of docs a single connection can be attached to.
    # Every join spends resolver + DB cycles (ACL + `ensure_snapshot`,
    # which may run a markdown→Y.Doc migration on first open), so an
    # unbounded loop is a cheap DoS. `_MAX_DOCS_PER_SID` is well above
    # any legitimate editor use — the SPA opens one doc per mounted
    # editor, and even a heavy multi-panel view stays single-digit.
    joined = _sid_docs.setdefault(request.sid, set())
    if doc_name not in joined and len(joined) >= _MAX_DOCS_PER_SID:
        emit('resolution-error',
             {'doc': doc_name, 'reason': 'too many docs joined on this connection'})
        return

    try:
        resolved = resolve_doc(doc_name, user_id)
    except DocResolutionError as exc:
        emit('resolution-error', {'doc': doc_name, 'reason': str(exc)})
        return

    if not resolved['exists']:
        emit('resolution-error', {'doc': doc_name, 'reason': 'not found'})
        return
    if not resolved['can_read']:
        emit('permission-denied', {'doc': doc_name, 'reason': 'no read access'})
        return

    # ensure_snapshot returns non-empty bytes on success — even for a
    # completely fresh doc, the value is the update for an empty Y.Doc
    # (small header). If the seeding raises, we don't want to admit the
    # client to the room since they'd be stuck with no state to apply.
    try:
        y_state_bytes = ensure_snapshot(doc_name, resolved['current_content'])
    except Exception:
        logger.exception('collab: ensure_snapshot failed for %s', doc_name)
        emit('resolution-error', {'doc': doc_name, 'reason': 'server error'})
        return

    join_room(doc_name)
    joined.add(doc_name)

    emit('sync-init', {
        'doc': doc_name,
        'y_state': base64.b64encode(y_state_bytes).decode('ascii'),
        'can_write': resolved['can_write'],
        'user': {
            'id': user_id,
            'name': _current_user_name(),
        },
    })


@socket_io.on('leave', namespace=NAMESPACE)
def on_leave(data):
    """Explicit leave (e.g. the editor unmounted)."""
    if not isinstance(data, dict):
        return
    doc_name = data.get('doc')
    if not isinstance(doc_name, str):
        return
    leave_room(doc_name)
    docs = _sid_docs.get(request.sid)
    if docs:
        docs.discard(doc_name)
    _maybe_flush_if_empty(doc_name)


@socket_io.on('sync', namespace=NAMESPACE)
def on_sync(data):
    """A Yjs update from one client — apply it to the authoritative
    Y.Doc, then fan out to the room.

    Payload: `{doc, update: base64}`. No `content_md` — server owns
    markdown rendering, we only accept opaque Yjs updates on the wire.

    Defense in depth:
      1. Sender must be a joined participant of `doc` (per our own
         `_sid_docs` mirror). Blocks a client from squirting an update
         into a room they never authenticated against.
      2. ACL is re-resolved on every message so a mid-session revoke
         takes effect immediately.
      3. Payload size is capped so a single client can't OOM the
         merge path or blow up the `collab_doc.y_state` blob.
      4. We only rebroadcast if the merge into the server's
         authoritative Y.Doc succeeded — a malformed update that fails
         `merge_updates` is dropped, not passed on to peers.
    """
    user_id = _current_user_id()
    if not user_id or not isinstance(data, dict):
        return
    doc_name = data.get('doc')
    update_b64 = data.get('update')
    if not isinstance(doc_name, str):
        return

    # (1) Sender-membership gate.
    if doc_name not in _sid_docs.get(request.sid, set()):
        emit('permission-denied',
             {'doc': doc_name, 'reason': 'not a participant of this doc'})
        return

    # (3) Size cap, before any DB work.
    if not isinstance(update_b64, str) or not update_b64:
        return
    if len(update_b64) > _MAX_UPDATE_B64_LEN:
        emit('resolution-error',
             {'doc': doc_name, 'reason': 'update too large or malformed'})
        return

    # (2) ACL re-check.
    try:
        resolved = resolve_doc(doc_name, user_id)
    except DocResolutionError:
        return
    if not resolved.get('can_write'):
        emit('permission-denied', {'doc': doc_name, 'reason': 'no write access'})
        return

    # (4) Merge into the server-authoritative Y.Doc. Only relay if the
    #     merge succeeded — a corrupt update stops here rather than
    #     poisoning peers.
    try:
        applied = apply_wire_update(doc_name, update_b64, user_id)
    except Exception:
        logger.exception('collab: apply_wire_update failed for %s', doc_name)
        return
    if applied is None:
        return

    emit('sync', {
        'doc': doc_name,
        'update': update_b64,
        'origin': _current_user_name(),
    }, to=doc_name, skip_sid=request.sid)


@socket_io.on('awareness', namespace=NAMESPACE)
def on_awareness(data):
    """Awareness (cursor + user identity) update from one client.

    Never persisted — ephemeral by design.

    Defenses:
      * Sender-membership gate: without this a client could squirt
        fake cursor decorations into a room they never authenticated
        against, just by knowing the doc name. Awareness carries the
        client-controlled `user.name` label so this would trivially
        enable impersonation-in-somebody-else's-room.
      * Size cap: awareness payloads are always small (cursor positions
        + a name). Anything above 64 KiB is a client bug or an attack.

    We deliberately skip the ACL re-resolve here — it's expensive per
    keystroke and the sender-membership gate already establishes that
    the sender was authorised at join time. A mid-session ACL revoke
    will still kick them out on their next `sync` (which does re-check),
    and the room they're spraying awareness into is one they legitimately
    have read access to right up until that point.
    """
    user_id = _current_user_id()
    if not user_id or not isinstance(data, dict):
        return
    doc_name = data.get('doc')
    update_b64 = data.get('update')
    if not isinstance(doc_name, str) or not isinstance(update_b64, str):
        return
    if len(update_b64) > _MAX_AWARENESS_B64_LEN:
        return

    if doc_name not in _sid_docs.get(request.sid, set()):
        # Silent drop — no `permission-denied` reply here because a
        # legitimate client will never hit this branch and we don't
        # want to give a scanner a signal to differentiate valid vs.
        # invalid doc_names.
        return

    # The client is welcome to spoof `user.name` inside the awareness
    # blob (we can't decode + rewrite it server-side without pulling in
    # a full Yjs Python implementation). Instead, we let the sender
    # attach their Yjs `client_id` in the message envelope, we map it
    # to the *authenticated* username on the server, and we rebroadcast
    # that mapping. Peers use the mapping to override the untrusted
    # label at render time (see client `SocketYjsProvider`).
    #
    # We ONLY broadcast the identity when it's new — the first time we
    # see a given client_id on this doc, or when its authenticated
    # user_id changes (which shouldn't happen in a single session but
    # is defensive). Broadcasting on every keystroke would trigger the
    # client's rewrite→re-render loop and produce visible cursor flicker.
    client_id = data.get('client_id')
    if isinstance(client_id, int):
        room_identities = _doc_client_identities.setdefault(doc_name, {})
        if room_identities.get(client_id) != user_id:
            room_identities[client_id] = user_id
            emit('awareness-identity', {
                'doc': doc_name,
                'client_id': client_id,
                'name': _current_user_name(),
                'user_id': user_id,
            }, to=doc_name)

    emit('awareness', {
        'doc': doc_name,
        'update': update_b64,
        'origin': _current_user_name(),
    }, to=doc_name, skip_sid=request.sid)


def register_collab_socket_handlers():
    """Called from app __init__ — forces this module to import so the
    `@socket_io.on(...)` decorators register. Mirrors the pattern used
    by the notification and case-notes handlers.
    """
    logger.debug('collab: /collab namespace registered')
    return None
