#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""SocketIO namespace for user-scoped notifications.

Clients open `/notifications` and emit `join` (no payload) to be added
to their own `user-<self.id>` room. That room name is derived entirely
from the authenticated session — the client CANNOT ask to join another
user's room. Server-emitted `new_notification` events are addressed to
`user-<recipient>` rooms only, so cross-user leakage requires either a
session-fixation bug elsewhere in the app OR joining someone else's
room; the latter is what this handler prevents.
"""

import logging

from flask import g, request
from flask_socketio import emit
from flask_socketio import join_room
from flask_socketio import leave_room

from app import socket_io
from app.blueprints.access_controls import is_user_authenticated
from app.blueprints.iris_user import iris_current_user
from app.business.auth import validate_auth_token


logger = logging.getLogger(__name__)


NAMESPACE = '/notifications'


# `g.auth_user` set by the auth-payload fallback in `on_connect` doesn't
# survive to subsequent events (each event gets its own request context),
# so we mirror the authenticated user id per-sid. See `_current_user_id`.
_sid_user_ids: dict[str, int] = {}


def _current_user_id():
    """Return the current authenticated user's id, or None."""
    # `iris_current_user` is a LocalProxy — resolve to the underlying
    # user object before touching attributes so we don't blow up on
    # unauthenticated sessions.
    user = iris_current_user._get_current_object()  # type: ignore[attr-defined]
    if user is not None:
        uid = getattr(user, 'id', None)
        if uid:
            return uid
    return _sid_user_ids.get(getattr(request, 'sid', None))


@socket_io.on('connect', namespace=NAMESPACE)
def on_connect(auth):
    """Require auth at connect time so unauthenticated sockets never
    persist in the namespace. Returning False rejects the connection.

    Auth resolution: session/header first, then fall back to the token
    supplied via socket.io's `auth` handshake payload — the browser
    strips custom headers on WS upgrade so a header-only path breaks
    behind SSO proxies. Matches the pattern used by the `/collab`
    namespace; see `collab_event_handlers.on_connect` for the writeup.

    We **auto-join** the caller's own user room here as part of the
    connect handshake — waiting for a follow-up `emit('join')` from
    the client left a race window (a few hundred ms on WebSocket, up
    to a full long-poll cycle on polling transport) where server-side
    emits landed in an empty room and were silently dropped. Since
    the room name is derived entirely from the authenticated session,
    the auto-join can't be abused to eavesdrop on someone else.
    """
    user_id = None

    if is_user_authenticated(request):
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

    if not user_id:
        return False

    _sid_user_ids[request.sid] = user_id
    join_room(f'user-{user_id}')
    logger.debug('notification namespace: user-%s joined on connect', user_id)
    return True


@socket_io.on('disconnect', namespace=NAMESPACE)
def on_disconnect():
    """Drop the per-sid identity so we don't leak entries as sockets
    churn. Room membership is cleaned up by flask-socketio itself.
    """
    _sid_user_ids.pop(request.sid, None)


@socket_io.on('join', namespace=NAMESPACE)
def on_join(_data=None):
    """Legacy join handler — kept for older clients that still emit
    `join` explicitly after connect. Idempotent: the connect handler
    already joined the room, so this is now a no-op ack.

    The `_data` payload is ignored entirely — the room is derived
    from the session id, NOT the payload.
    """
    user_id = _current_user_id()
    if not user_id:
        return
    # Idempotent — flask-socketio's join_room is a no-op when the
    # session is already in the room.
    join_room(f'user-{user_id}')
    emit('joined', {'ok': True, 'user_id': user_id})


@socket_io.on('leave', namespace=NAMESPACE)
def on_leave(_data=None):
    user_id = _current_user_id()
    if not user_id:
        return
    leave_room(f'user-{user_id}')


def register_notification_socket_handlers():
    """Called from app __init__ after the other socket handlers.

    The `@socket_io.on` decorators above register at import time, so
    this function is a no-op body — its purpose is to force the module
    to be imported (which triggers those decorators). Mirrors the
    pattern used by the case / notes / update handlers.
    """
    return None
