#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Notification service — the single public API modules and hook
listeners call to fire notifications.

Design:

* `notify()` is the atomic write path: resolve settings for
  (user, event_type), insert a `notification` row if in-app is
  enabled, emit over SocketIO, and hand off the email side to a
  Celery task if email is enabled.
* `notify_many()` fans out over a set of user ids using a single
  batched setting-resolution query (see `_resolve_channels_bulk`)
  so a note with 50 mentions doesn't fire 100 setting lookups.
* Settings resolution is two-tier: per-user row wins, else admin
  default, else `_DEFAULT_CHANNEL_STATE` (the shipped built-in).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable
from typing import Optional
from typing import Sequence

from sqlalchemy import and_
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import db
from app.models.notifications import CHANNELS
from app.models.notifications import EVENT_TYPES
from app.models.notifications import Notification
from app.models.notifications import NotificationSetting


logger = logging.getLogger(__name__)


# What every event type defaults to when neither the user nor the admin
# has overridden it. Kept intentionally opt-in-heavy for in-app (all
# events fire in-app by default so a fresh install feels alive) and
# opt-out-light for email (no email spam by default — the admin has to
# turn it on).
_DEFAULT_CHANNEL_STATE = {
    'mention':               {'in_app': True,  'email': False},
    'task_assigned':         {'in_app': True,  'email': False},
    'case_state_change':     {'in_app': True,  'email': False},
    'case_assigned':         {'in_app': True,  'email': False},
    'alert_assigned':        {'in_app': True,  'email': False},
    'alert_escalated':       {'in_app': True,  'email': False},
    'war_room_message':      {'in_app': True,  'email': False},
    'war_room_thread_reply': {'in_app': True,  'email': False},
    # Modules opt in per-invocation — see `notify(..., default_channels)`
    # for the override knob. Default here is in-app only.
    'module_custom':         {'in_app': True,  'email': False},
}


def _safe_socket_emit(event_name: str, payload: dict, room: str) -> None:
    """Emit to SocketIO, swallowing errors.

    We import lazily and wrap in try/except because:
    * The Celery worker process doesn't hold a live SocketIO server —
      importing at module top would raise there.
    * The REST write already succeeded when we get here; a socket
      hiccup should not fail the request.
    """
    try:
        from app import socket_io
    except Exception:
        return
    try:
        socket_io.emit(event_name, payload, room=room, namespace='/notifications')
    except Exception as exc:
        logger.warning('SocketIO emit failed for %s -> %s: %s',
                       event_name, room, exc)


def _resolve_channels(user_id: int, event_type: str,
                      override_defaults: Optional[dict] = None) -> dict:
    """Return the effective `{channel: enabled}` map for one user.

    Precedence: per-user row > admin default (user_id NULL) > shipped
    built-in default (or `override_defaults` if the caller passed one,
    used by modules that want a different baseline for their custom
    event type).
    """
    baseline = dict(override_defaults or _DEFAULT_CHANNEL_STATE.get(
        event_type, {'in_app': True, 'email': False}))

    rows = (
        NotificationSetting.query
        .filter(NotificationSetting.event_type == event_type)
        .filter(or_(NotificationSetting.user_id == user_id,
                    NotificationSetting.user_id.is_(None)))
        .all()
    )
    admin_map = {}
    user_map = {}
    for row in rows:
        target = user_map if row.user_id == user_id else admin_map
        target[row.channel] = bool(row.enabled)

    effective = {}
    for channel in CHANNELS:
        if channel in user_map:
            effective[channel] = user_map[channel]
        elif channel in admin_map:
            effective[channel] = admin_map[channel]
        else:
            effective[channel] = baseline.get(channel, False)
    return effective


def _resolve_channels_bulk(user_ids: Sequence[int], event_type: str,
                           override_defaults: Optional[dict] = None
                           ) -> dict:
    """Batched version returning `{user_id: {channel: bool}}`.

    Uses one query to pull all admin defaults + all user rows for the
    given user_ids + event_type. Big win for @-mentions that fan out.
    """
    baseline = dict(override_defaults or _DEFAULT_CHANNEL_STATE.get(
        event_type, {'in_app': True, 'email': False}))

    if not user_ids:
        return {}
    user_ids = list({int(u) for u in user_ids})

    rows = (
        NotificationSetting.query
        .filter(NotificationSetting.event_type == event_type)
        .filter(or_(
            NotificationSetting.user_id.in_(user_ids),
            NotificationSetting.user_id.is_(None),
        ))
        .all()
    )
    admin_map: dict = {}
    per_user: dict = {uid: {} for uid in user_ids}
    for row in rows:
        if row.user_id is None:
            admin_map[row.channel] = bool(row.enabled)
        elif row.user_id in per_user:
            per_user[row.user_id][row.channel] = bool(row.enabled)

    result = {}
    for uid in user_ids:
        overrides = per_user.get(uid, {})
        effective = {}
        for channel in CHANNELS:
            if channel in overrides:
                effective[channel] = overrides[channel]
            elif channel in admin_map:
                effective[channel] = admin_map[channel]
            else:
                effective[channel] = baseline.get(channel, False)
        result[uid] = effective
    return result


def notify(user_id: int,
           event_type: str,
           title: str,
           body: Optional[str] = None,
           link: Optional[str] = None,
           source_type: Optional[str] = None,
           source_id: Optional[int] = None,
           default_channels: Optional[dict] = None) -> Optional[Notification]:
    """Fire a single notification.

    Returns the persisted `Notification` row when in-app was enabled,
    None when the user has all channels disabled (nothing was written).

    * `default_channels` — module escape hatch: modules calling this
      with `event_type='module_custom'` can pass a custom baseline
      (e.g. `{'in_app': True, 'email': True}`) to opt themselves into
      email delivery by default.
    """
    if not user_id or not event_type or not title:
        # Silently ignore — a hook listener passing None means "no
        # recipient was found" (self-mention, deleted user), which is
        # not an error path. Raising here would bubble into user-facing
        # save flows.
        return None

    channels = _resolve_channels(user_id, event_type,
                                 override_defaults=default_channels)

    if not any(channels.values()):
        return None

    notification: Optional[Notification] = None
    if channels.get('in_app'):
        notification = Notification(
            user_id=user_id,
            event_type=event_type,
            title=title[:255],
            body=body,
            link=link[:1024] if link else None,
            source_type=source_type,
            source_id=source_id,
        )
        db.session.add(notification)
        db.session.commit()

        _safe_socket_emit('new_notification', {
            'id': notification.id,
            'event_type': notification.event_type,
            'title': notification.title,
            'body': notification.body,
            'link': notification.link,
            'source_type': notification.source_type,
            'source_id': notification.source_id,
            'created_at': notification.created_at.isoformat(),
        }, room=f'user-{user_id}')

    if channels.get('email') and notification is not None:
        # Email delivery is asynchronous — hand off to a Celery task
        # so a slow SMTP endpoint doesn't stall the request that
        # fired the notification. The task itself checks whether
        # SMTP is configured and short-circuits if disabled.
        try:
            from app.iris_engine.mail.outbound import send_notification_email
            send_notification_email.delay(notification.id)
        except Exception:
            # Never let a mail hand-off fail the request. The
            # in-app path already succeeded and there's no user-
            # visible reason to error out.
            logger.exception(
                'Failed to enqueue notification email for user=%s event=%s',
                user_id, event_type,
            )

    return notification


def notify_many(user_ids: Iterable[int],
                event_type: str,
                title: str,
                body: Optional[str] = None,
                link: Optional[str] = None,
                source_type: Optional[str] = None,
                source_id: Optional[int] = None,
                exclude_user_ids: Optional[Iterable[int]] = None,
                default_channels: Optional[dict] = None) -> list:
    """Fan-out helper. Returns the list of persisted `Notification`
    rows (skips users whose channels are all disabled).

    * `exclude_user_ids` — typically the actor (don't notify yourself
      about your own action). Cheaper than filtering pre-call.
    """
    exclude = {int(u) for u in (exclude_user_ids or [])}
    targets = [int(u) for u in user_ids if u and int(u) not in exclude]
    targets = list(dict.fromkeys(targets))  # dedupe, preserve order
    if not targets:
        return []

    channels_by_user = _resolve_channels_bulk(
        targets, event_type, override_defaults=default_channels)

    created = []
    for uid in targets:
        channels = channels_by_user.get(uid, {})
        if not any(channels.values()):
            continue
        # Delegate the per-user work to `notify()` so the socket emit
        # and the (future) email hand-off share one code path. Using
        # per-user commits keeps the transaction small and mirrors the
        # existing hook-handler pattern.
        n = notify(
            user_id=uid,
            event_type=event_type,
            title=title,
            body=body,
            link=link,
            source_type=source_type,
            source_id=source_id,
            default_channels=default_channels,
        )
        if n is not None:
            created.append(n)
    return created


def list_for_user(user_id: int,
                  unread_only: bool = False,
                  limit: int = 50,
                  before_id: Optional[int] = None) -> list:
    """Bell dropdown feed. Newest first, cursor by id."""
    limit = max(1, min(int(limit), 200))
    q = Notification.query.filter(Notification.user_id == user_id)
    if unread_only:
        q = q.filter(Notification.read_at.is_(None))
    if before_id:
        q = q.filter(Notification.id < int(before_id))
    return (q.order_by(Notification.id.desc()).limit(limit).all())


def unread_count(user_id: int) -> int:
    return (
        Notification.query
        .filter(Notification.user_id == user_id)
        .filter(Notification.read_at.is_(None))
        .count()
    )


def mark_read(user_id: int,
              ids: Optional[Iterable[int]] = None,
              all_: bool = False) -> int:
    """Mark notifications read for a user. Returns rows affected.

    Callers MUST scope by `user_id` (the current auth session). The
    query below is scoped defensively — even if a client passes IDs
    belonging to a different user, we only update rows where
    `user_id` matches.
    """
    now = datetime.utcnow()
    q = Notification.query.filter(Notification.user_id == user_id)
    if not all_:
        cleaned = [int(i) for i in (ids or []) if i]
        if not cleaned:
            return 0
        q = q.filter(Notification.id.in_(cleaned))
    # Skip rows already read — cheaper and keeps `read_at` stable.
    q = q.filter(Notification.read_at.is_(None))
    affected = q.update({Notification.read_at: now},
                        synchronize_session=False)
    db.session.commit()
    return int(affected or 0)


def clear(user_id: int,
          ids: Optional[Iterable[int]] = None,
          all_: bool = False) -> int:
    """Permanently delete notifications for a user. Returns rows deleted.

    Distinct from `mark_read` — this removes the rows entirely so the
    bell dropdown no longer surfaces them. Same defensive scoping:
    even with foreign IDs in the payload, only rows owned by
    `user_id` are affected.
    """
    q = Notification.query.filter(Notification.user_id == user_id)
    if not all_:
        cleaned = [int(i) for i in (ids or []) if i]
        if not cleaned:
            return 0
        q = q.filter(Notification.id.in_(cleaned))
    affected = q.delete(synchronize_session=False)
    db.session.commit()
    return int(affected or 0)


def get_effective_settings(user_id: int) -> dict:
    """Return the full `{event_type: {channel: enabled}}` map for one
    user, merging admin defaults + per-user rows + shipped defaults.

    Used by the profile "Notifications" tab to render the checkbox
    grid.
    """
    rows = (
        NotificationSetting.query
        .filter(or_(NotificationSetting.user_id == user_id,
                    NotificationSetting.user_id.is_(None)))
        .all()
    )
    admin_map: dict = {}
    user_map: dict = {}
    for row in rows:
        target = admin_map if row.user_id is None else user_map
        target.setdefault(row.event_type, {})[row.channel] = bool(row.enabled)

    result = {}
    for event_type in EVENT_TYPES:
        baseline = _DEFAULT_CHANNEL_STATE.get(
            event_type, {'in_app': True, 'email': False})
        merged = {}
        for channel in CHANNELS:
            if channel in user_map.get(event_type, {}):
                merged[channel] = user_map[event_type][channel]
            elif channel in admin_map.get(event_type, {}):
                merged[channel] = admin_map[event_type][channel]
            else:
                merged[channel] = baseline.get(channel, False)
        result[event_type] = merged
    return result


def get_admin_settings() -> dict:
    """Return the admin defaults grid — what /manage/notifications
    edits. Missing rows fall back to shipped defaults so the admin UI
    can show a complete grid without seeding first."""
    rows = (
        NotificationSetting.query
        .filter(NotificationSetting.user_id.is_(None))
        .all()
    )
    admin_map: dict = {}
    for row in rows:
        admin_map.setdefault(row.event_type, {})[row.channel] = bool(row.enabled)

    result = {}
    for event_type in EVENT_TYPES:
        baseline = _DEFAULT_CHANNEL_STATE.get(
            event_type, {'in_app': True, 'email': False})
        merged = {}
        for channel in CHANNELS:
            merged[channel] = admin_map.get(event_type, {}).get(
                channel, baseline.get(channel, False))
        result[event_type] = merged
    return result


def _upsert_setting(user_id: Optional[int], event_type: str,
                    channel: str, enabled: bool) -> None:
    """Postgres upsert on the (user_id, event_type, channel) key.

    Uses `ON CONFLICT` on the composite unique constraint we declared
    in the migration. For admin rows (user_id IS NULL) the partial
    index `uq_notification_setting_admin_default` provides the same
    guarantee since the plain constraint treats NULLs as distinct.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f'Unknown event_type: {event_type}')
    if channel not in CHANNELS:
        raise ValueError(f'Unknown channel: {channel}')

    if user_id is None:
        # Admin row: manual upsert via the partial index because
        # ON CONFLICT + WHERE-partial-index needs the index_predicate
        # spelled out. Cheaper here to fetch-then-update-or-insert.
        existing = (
            NotificationSetting.query
            .filter(NotificationSetting.user_id.is_(None))
            .filter(NotificationSetting.event_type == event_type)
            .filter(NotificationSetting.channel == channel)
            .first()
        )
        if existing is not None:
            existing.enabled = bool(enabled)
        else:
            db.session.add(NotificationSetting(
                user_id=None, event_type=event_type,
                channel=channel, enabled=bool(enabled)))
        db.session.commit()
        return

    stmt = pg_insert(NotificationSetting.__table__).values(
        user_id=int(user_id),
        event_type=event_type,
        channel=channel,
        enabled=bool(enabled),
    ).on_conflict_do_update(
        constraint='uq_notification_setting_scope',
        set_={'enabled': bool(enabled), 'updated_at': datetime.utcnow()},
    )
    db.session.execute(stmt)
    db.session.commit()


def upsert_user_settings(user_id: int, settings: dict) -> dict:
    """Bulk upsert per-user settings. `settings` shape:
    `{event_type: {channel: bool}}`. Silently drops unknown
    events/channels rather than raising so a partial UI submission
    (e.g. rolling upgrade with a new event type the SPA doesn't
    know yet) still saves what it can."""
    for event_type, channel_map in (settings or {}).items():
        if event_type not in EVENT_TYPES:
            continue
        if not isinstance(channel_map, dict):
            continue
        for channel, enabled in channel_map.items():
            if channel not in CHANNELS:
                continue
            _upsert_setting(int(user_id), event_type, channel, bool(enabled))
    return get_effective_settings(int(user_id))


def upsert_admin_settings(settings: dict) -> dict:
    """Admin-only bulk upsert. Same input shape as
    `upsert_user_settings` but writes rows with `user_id IS NULL`.
    Caller MUST enforce admin permission before calling."""
    for event_type, channel_map in (settings or {}).items():
        if event_type not in EVENT_TYPES:
            continue
        if not isinstance(channel_map, dict):
            continue
        for channel, enabled in channel_map.items():
            if channel not in CHANNELS:
                continue
            _upsert_setting(None, event_type, channel, bool(enabled))
    return get_admin_settings()


def seed_admin_defaults() -> None:
    """Insert the shipped defaults as admin rows if they are absent.

    Called from post_init on first boot. Idempotent — existing rows
    are left untouched so an operator's manual toggles survive a
    restart.
    """
    for event_type, channel_state in _DEFAULT_CHANNEL_STATE.items():
        for channel, enabled in channel_state.items():
            exists = (
                NotificationSetting.query
                .filter(NotificationSetting.user_id.is_(None))
                .filter(NotificationSetting.event_type == event_type)
                .filter(NotificationSetting.channel == channel)
                .first()
            )
            if exists is None:
                db.session.add(NotificationSetting(
                    user_id=None,
                    event_type=event_type,
                    channel=channel,
                    enabled=bool(enabled),
                ))
    db.session.commit()


# Silences unused-import warnings for `and_` in tools that lint on
# import graph — kept in the file because future ACL filters (see
# hook_listeners.py) will use compound conditions here.
_ = and_
