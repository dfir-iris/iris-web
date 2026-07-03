#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""v2 REST endpoints for the notification core.

Two blueprints:

* `notifications_blueprint` — mounted at `/notifications` — user-scoped
  reads (list, unread count, mark read) and the per-user preferences
  under `/notification-settings`.
* `admin_notifications_blueprint` — mounted at
  `/manage/notification-settings` — admin-only defaults.

Every user-scoped endpoint answers only for `iris_current_user.id`.
Passing another user id in a body/query is silently ignored — the
service layer scopes on the session id regardless.
"""

from __future__ import annotations

from flask import Blueprint
from flask import request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.iris_engine.notifications.service import clear as clear_notifications
from app.iris_engine.notifications.service import get_admin_settings
from app.iris_engine.notifications.service import get_effective_settings
from app.iris_engine.notifications.service import list_for_user
from app.iris_engine.notifications.service import mark_read
from app.iris_engine.notifications.service import unread_count
from app.iris_engine.notifications.service import upsert_admin_settings
from app.iris_engine.notifications.service import upsert_user_settings
from app.models.authorization import Permissions
from app.models.notifications import CHANNELS
from app.models.notifications import EVENT_TYPES
from app.models.notifications import Notification
from app.models.notifications import NotificationSetting


notifications_blueprint = Blueprint(
    'notifications_rest_v2', __name__, url_prefix='/notifications')


def _serialize(row):
    return {
        'id': row.id,
        'event_type': row.event_type,
        'title': row.title,
        'body': row.body,
        'link': row.link,
        'source_type': row.source_type,
        'source_id': row.source_id,
        'read_at': row.read_at.isoformat() if row.read_at else None,
        'created_at': row.created_at.isoformat() if row.created_at else None,
    }


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------

@notifications_blueprint.get('')
@ac_api_requires()
def get_notifications():
    """List the current user's notifications.

    Query params:
    * `unread_only` — 'true' filters to unread rows only
    * `limit` — default 50, max 200
    * `before_id` — cursor for infinite scroll
    """
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    limit = request.args.get('limit', default=50, type=int)
    before_id = request.args.get('before_id', type=int)

    rows = list_for_user(
        user_id=iris_current_user.id,
        unread_only=unread_only,
        limit=limit,
        before_id=before_id,
    )
    return response_api_success({
        'data': [_serialize(r) for r in rows],
        'unread_count': unread_count(iris_current_user.id),
    })


@notifications_blueprint.get('/unread-count')
@ac_api_requires()
def get_unread_count():
    """Bell badge poll — cheap `SELECT count(*)`."""
    return response_api_success({
        'unread_count': unread_count(iris_current_user.id),
    })


@notifications_blueprint.post('/mark-read')
@ac_api_requires()
def post_mark_read():
    """Mark notifications read. Body: `{"ids": [...]}` OR `{"all": true}`.

    Any id in `ids` that doesn't belong to the current user is
    silently ignored (the service layer filters on user_id).
    """
    payload = request.get_json(silent=True) or {}
    all_flag = bool(payload.get('all'))
    raw_ids = payload.get('ids') or []
    if not all_flag and not isinstance(raw_ids, list):
        return response_api_error('ids must be an array')

    ids = []
    if not all_flag:
        for i in raw_ids:
            try:
                ids.append(int(i))
            except (TypeError, ValueError):
                # Ignore garbage rather than 400 — the client shouldn't
                # have to sanitise, and marking a subset is fine.
                continue
        if not ids:
            return response_api_error('No valid ids provided')

    affected = mark_read(
        user_id=iris_current_user.id,
        ids=ids if not all_flag else None,
        all_=all_flag,
    )
    return response_api_success({
        'affected': affected,
        'unread_count': unread_count(iris_current_user.id),
    })


@notifications_blueprint.post('/clear')
@ac_api_requires()
def post_clear():
    """Permanently delete notifications. Body: `{"ids": [...]}` OR
    `{"all": true}`.

    Same defensive scoping as mark-read — the service only ever
    touches rows owned by the session user.
    """
    payload = request.get_json(silent=True) or {}
    all_flag = bool(payload.get('all'))
    raw_ids = payload.get('ids') or []
    if not all_flag and not isinstance(raw_ids, list):
        return response_api_error('ids must be an array')

    ids = []
    if not all_flag:
        for i in raw_ids:
            try:
                ids.append(int(i))
            except (TypeError, ValueError):
                continue
        if not ids:
            return response_api_error('No valid ids provided')

    affected = clear_notifications(
        user_id=iris_current_user.id,
        ids=ids if not all_flag else None,
        all_=all_flag,
    )
    return response_api_success({
        'affected': affected,
        'unread_count': unread_count(iris_current_user.id),
    })


# ---------------------------------------------------------------------------
# User preferences
# ---------------------------------------------------------------------------

@notifications_blueprint.get('/settings')
@ac_api_requires()
def get_settings():
    """Return the effective settings grid for the current user.

    Shape: `{event_types: [...], channels: [...],
    settings: {event: {channel: bool}}}` — the SPA renders the grid
    from `event_types` × `channels` and marks each cell from
    `settings`.
    """
    return response_api_success({
        'event_types': list(EVENT_TYPES),
        'channels': list(CHANNELS),
        'settings': get_effective_settings(iris_current_user.id),
    })


@notifications_blueprint.put('/settings')
@ac_api_requires()
def put_settings():
    """Upsert per-user settings. Body: `{settings: {event: {channel: bool}}}`.

    Unknown events/channels are dropped; the service returns the
    effective merged view so the SPA can render post-save without
    another round-trip.
    """
    payload = request.get_json(silent=True) or {}
    settings = payload.get('settings')
    if not isinstance(settings, dict):
        return response_api_error('settings must be an object')

    merged = upsert_user_settings(iris_current_user.id, settings)
    return response_api_success({
        'event_types': list(EVENT_TYPES),
        'channels': list(CHANNELS),
        'settings': merged,
    })


# ---------------------------------------------------------------------------
# Diagnostics — end-to-end health check for the notifications pipeline
# ---------------------------------------------------------------------------

@notifications_blueprint.get('/_diag')
@ac_api_requires()
def get_diag():
    """Report the state of every link in the notification chain.

    Meant for interactive debugging when notifications feel broken. Each
    section reports a boolean-ish signal plus a short note so the caller
    can pinpoint which link is down without SSH'ing into the pod.

    Sections:
      * `hook_listeners` — is `call_modules_hook` wrapped, and how many
        of the expected hook names are mapped?
      * `socket_namespace` — is the `/notifications` namespace attached
        to the running SocketIO server?
      * `db` — do the tables exist and how many rows are in them?
      * `settings` — the caller's effective settings + admin defaults
        (redacted to booleans only, no PII).
      * `recent` — the 5 most recent rows for the caller, so we can tell
        "the write happened, socket delivery failed" apart from "the
        write never happened".
    """
    import time
    from sqlalchemy import inspect as sa_inspect

    from app import socket_io
    from app.db import db
    from app.iris_engine.notifications import hook_listeners
    from app.iris_engine.notifications.hook_listeners import _HOOK_MAP

    report = {'checked_at': time.time()}

    # --- Hook listeners --------------------------------------------------
    # `register_notification_listeners()` sets `_notifications_wrapped`
    # on the module_handler module. If that's False, none of the fire
    # sites will produce a notification, no matter what else is right.
    try:
        wrapped = bool(getattr(hook_listeners._mh, '_notifications_wrapped', False))
    except Exception as exc:
        wrapped = False
        report['hook_listeners_error'] = str(exc)
    report['hook_listeners'] = {
        'wrapped': wrapped,
        'mapped_hooks': sorted(_HOOK_MAP.keys()),
        'mapped_hook_count': len(_HOOK_MAP),
        'note': (
            'call_modules_hook is monkey-patched at boot via '
            'register_notification_listeners(). If wrapped=False, no '
            'notifications will ever fire — check post_init.py:1366-1368 '
            'and IRIS_INITIALIZE_IFACE env var.'
        ),
    }

    # --- Socket namespace ------------------------------------------------
    # flask-socketio stores per-namespace handler dicts on the server.
    # Presence of '/notifications' in `handlers` means the decorators in
    # notification_event_handlers.py actually ran. If it's missing, the
    # frontend socket connection will get a namespace error and go dark.
    try:
        server_handlers = getattr(socket_io.server, 'handlers', {})
        namespace_registered = '/notifications' in server_handlers
        events = sorted(server_handlers.get('/notifications', {}).keys()) \
            if namespace_registered else []
    except Exception as exc:
        namespace_registered = False
        events = []
        report['socket_namespace_error'] = str(exc)
    report['socket_namespace'] = {
        'registered': namespace_registered,
        'events': events,
        'note': (
            'If registered=False, either register_notification_socket_handlers() '
            "wasn't called in app/__init__.py or the import failed silently. "
            'Namespace must exist for real-time bell updates; frontend falls '
            'back to 30s polling but that only works if the REST feed works.'
        ),
    }

    # --- Database --------------------------------------------------------
    try:
        insp = sa_inspect(db.engine)
        table_names = set(insp.get_table_names())
        notification_table = 'notification' in table_names
        settings_table = 'notification_setting' in table_names
        total_rows = (
            db.session.query(Notification).count()
            if notification_table else None
        )
        for_current_user = (
            db.session.query(Notification)
            .filter(Notification.user_id == iris_current_user.id)
            .count()
            if notification_table else None
        )
    except Exception as exc:
        notification_table = None
        settings_table = None
        total_rows = None
        for_current_user = None
        report['db_error'] = str(exc)
    report['db'] = {
        'notification_table_exists': notification_table,
        'notification_setting_table_exists': settings_table,
        'total_notifications': total_rows,
        'notifications_for_current_user': for_current_user,
        'note': (
            'If either table is missing, migration e7b1f4a8c920 never ran. '
            'total_notifications==0 with wrapped=True and a recent mention '
            "means the listener chose to skip (self-mention? user doesn't "
            'exist?) — check the app log for _safe() catches.'
        ),
    }

    # --- Settings for the current user -----------------------------------
    # The most common "everything works but nothing arrives" cause is a
    # setting where every in_app cell is False. Report as booleans grouped
    # by event type so the caller can eyeball it.
    try:
        effective = get_effective_settings(iris_current_user.id)
        admin = get_admin_settings()
    except Exception as exc:
        effective = None
        admin = None
        report['settings_error'] = str(exc)
    report['settings'] = {
        'event_types': list(EVENT_TYPES),
        'channels': list(CHANNELS),
        'effective_for_current_user': effective,
        'admin_defaults': admin,
        'note': (
            'A row with in_app=False across every event will produce a bell '
            'that never lights up. Note that admin defaults seed at boot via '
            'seed_admin_defaults() — if admin_defaults is empty, that seed '
            'never ran either.'
        ),
    }

    # --- Recent rows for the caller --------------------------------------
    # Confirms that at least SOMETHING is being written. If this is empty
    # after triggering a mention, the listener path is broken. If this is
    # populated but the bell shows 0, the frontend/socket path is broken.
    try:
        recent_rows = (
            db.session.query(Notification)
            .filter(Notification.user_id == iris_current_user.id)
            .order_by(Notification.created_at.desc())
            .limit(5)
            .all()
        )
        recent = [
            {
                'id': r.id,
                'event_type': r.event_type,
                'title': r.title,
                'created_at': r.created_at.isoformat() if r.created_at else None,
                'read_at': r.read_at.isoformat() if r.read_at else None,
            }
            for r in recent_rows
        ]
    except Exception as exc:
        recent = None
        report['recent_error'] = str(exc)
    report['recent'] = recent

    # --- Overall verdict -------------------------------------------------
    # Rolled-up boolean the caller can grep for.
    healthy = bool(
        report['hook_listeners']['wrapped']
        and report['socket_namespace']['registered']
        and report['db']['notification_table_exists']
    )
    report['healthy'] = healthy

    return response_api_success(report)


# ---------------------------------------------------------------------------
# Admin defaults — separate blueprint, permission-gated
# ---------------------------------------------------------------------------

admin_notifications_blueprint = Blueprint(
    'admin_notifications_rest_v2', __name__,
    url_prefix='/manage/notification-settings',
)


@admin_notifications_blueprint.get('')
@ac_api_requires(Permissions.server_administrator)
def get_admin():
    return response_api_success({
        'event_types': list(EVENT_TYPES),
        'channels': list(CHANNELS),
        'settings': get_admin_settings(),
    })


@admin_notifications_blueprint.put('')
@ac_api_requires(Permissions.server_administrator)
def put_admin():
    payload = request.get_json(silent=True) or {}
    settings = payload.get('settings')
    if not isinstance(settings, dict):
        return response_api_error('settings must be an object')

    merged = upsert_admin_settings(settings)
    return response_api_success({
        'event_types': list(EVENT_TYPES),
        'channels': list(CHANNELS),
        'settings': merged,
    })
