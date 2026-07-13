#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""Notification core: the `notification` and `notification_setting` tables.

A `Notification` row is a *materialised* event addressed to one user: the
title/body/link are rendered at fire time and persisted on the row so the
bell dropdown survives deletion of the source object (deleting a case
should not erase the mention notification that pointed at it — the user
still needs to know they were pinged).

`NotificationSetting` implements a two-tier config: admin rows have
`user_id IS NULL` and define the org default, per-user rows override.
The effective setting for `(user, event_type, channel)` is the user row
if present, else the admin row, else the built-in default (see
`iris_engine/notifications/service.py`).
"""

from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db import db


# Notification event types. Kept as free-form strings (not a DB enum) so
# modules can register their own event types via the `module_custom`
# convention without a migration. The set below is what the core fires;
# admin defaults + user prefs are only seeded for these.
EVENT_TYPES = (
    'mention',
    'task_assigned',
    'case_state_change',
    'case_assigned',
    'alert_assigned',
    'alert_escalated',
    'war_room_message',
    'war_room_thread_reply',
    'module_custom',
)

CHANNELS = ('in_app', 'email')


class Notification(db.Model):
    __tablename__ = 'notification'

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('user.id', ondelete='CASCADE'),
                     nullable=False, index=True)
    event_type = Column(String(64), nullable=False)

    # Rendered at fire time so deleting the source object doesn't nuke
    # the notification. Kept as short strings to keep the bell payload
    # small — the SPA follows `link` for the full context.
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    link = Column(String(1024), nullable=True)

    # Polymorphic pointer for dedupe and cleanup jobs. Not a FK — the
    # source table varies (notes, comments, cases, alerts, war_room …).
    source_type = Column(String(64), nullable=True)
    source_id = Column(BigInteger, nullable=True)

    # `read_at IS NULL` = unread. The bell dropdown filters on this.
    read_at = Column(DateTime, nullable=True)
    # Set once the outbound email has been handed off to SMTP (or the
    # user's email channel is disabled, so we skipped it). Lets the
    # /notifications feed distinguish "queued" vs "delivered" if we ever
    # add a retry surface.
    emailed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False,
                        server_default=func.now())

    user = relationship('User', backref='notifications')

    __table_args__ = (
        # Powers the bell dropdown: unread rows for one user, newest
        # first. The `read_at IS NULL` predicate is highly selective for
        # active users, so this compound index keeps that hot path cheap.
        Index('ix_notification_user_unread',
              'user_id', 'read_at', 'created_at'),
    )


class NotificationSetting(db.Model):
    __tablename__ = 'notification_setting'

    id = Column(BigInteger, primary_key=True)
    # NULL = admin default (org-wide). Not-NULL = per-user override.
    # `ondelete=CASCADE` so removing a user drops their prefs; admin
    # defaults (NULL) survive since no FK matches.
    user_id = Column(BigInteger, ForeignKey('user.id', ondelete='CASCADE'),
                     nullable=True)
    event_type = Column(String(64), nullable=False)
    channel = Column(String(16), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)

    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    user = relationship('User')

    __table_args__ = (
        # We rely on this unique constraint to upsert prefs in one
        # statement. Admin defaults (user_id NULL) and per-user rows
        # live in the same table but never collide because Postgres
        # treats NULLs as distinct in a unique index — that's fine here
        # because we only ever want ONE admin default per (event,
        # channel), and we enforce that via a partial index in the
        # migration (uq_notification_setting_admin_default).
        UniqueConstraint('user_id', 'event_type', 'channel',
                         name='uq_notification_setting_scope'),
    )
