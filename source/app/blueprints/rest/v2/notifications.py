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
