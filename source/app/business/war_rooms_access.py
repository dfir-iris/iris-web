#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""Access-control helpers for war rooms.

Mirrors the case ACL precedence (default → group → user) but routes
to war-room-specific join tables. Kept in its own module so the
generic case ACL plumbing in `business.access_controls` stays focused
on its existing surface.
"""

from sqlalchemy import and_

from app.db import db
from app.models.authorization import GroupWarRoomAccess
from app.models.authorization import Permissions
from app.models.authorization import UserGroup
from app.models.authorization import UserWarRoomAccess
from app.models.authorization import UserWarRoomEffectiveAccess
from app.models.authorization import WarRoomAccessLevel
from app.models.authorization import ac_flag_match_mask
from app.models.authorization import ac_has_permission_server_administrator


def _get_effective_access_level(user_id, war_room_id):
    row = (
        UserWarRoomEffectiveAccess.query
        .filter(and_(
            UserWarRoomEffectiveAccess.user_id == user_id,
            UserWarRoomEffectiveAccess.war_room_id == war_room_id,
        ))
        .with_entities(UserWarRoomEffectiveAccess.access_level)
        .first()
    )
    return row.access_level if row else None


def _recompute_effective_access_level(user_id, war_room_id):
    """Compute precedence chain and return the highest access level.

    Order: group access overwrites default (None == deny_all), user access
    overwrites group access. Last write wins.
    """
    access_level = None

    group_row = (
        GroupWarRoomAccess.query
        .with_entities(GroupWarRoomAccess.access_level)
        .filter(and_(
            UserGroup.user_id == user_id,
            UserGroup.group_id == GroupWarRoomAccess.group_id,
            GroupWarRoomAccess.war_room_id == war_room_id,
        ))
        .first()
    )
    if group_row:
        access_level = group_row.access_level

    user_row = (
        UserWarRoomAccess.query
        .with_entities(UserWarRoomAccess.access_level)
        .filter(and_(
            UserWarRoomAccess.user_id == user_id,
            UserWarRoomAccess.war_room_id == war_room_id,
        ))
        .first()
    )
    if user_row:
        access_level = user_row.access_level

    return access_level


def set_war_room_effective_access_for_user(user_id, war_room_id, access_level):
    existing = UserWarRoomEffectiveAccess.query.filter(and_(
        UserWarRoomEffectiveAccess.user_id == user_id,
        UserWarRoomEffectiveAccess.war_room_id == war_room_id,
    )).all()

    if len(existing) > 1:
        for row in existing:
            db.session.delete(row)
        db.session.commit()
        existing = []

    if existing:
        existing[0].access_level = access_level
    else:
        row = UserWarRoomEffectiveAccess()
        row.user_id = user_id
        row.war_room_id = war_room_id
        row.access_level = access_level
        db.session.add(row)

    db.session.commit()


def set_user_war_room_access(user_id, war_room_id, access_level):
    """Grant explicit per-user access to a war room and refresh the cache."""
    rows = UserWarRoomAccess.query.filter(and_(
        UserWarRoomAccess.user_id == user_id,
        UserWarRoomAccess.war_room_id == war_room_id,
    )).all()

    if len(rows) > 1:
        for r in rows:
            db.session.delete(r)
        db.session.commit()
        rows = []

    if rows:
        rows[0].access_level = access_level
    else:
        row = UserWarRoomAccess()
        row.user_id = user_id
        row.war_room_id = war_room_id
        row.access_level = access_level
        db.session.add(row)

    db.session.commit()

    set_war_room_effective_access_for_user(user_id, war_room_id, access_level)


def remove_user_war_room_access(user_id, war_room_id):
    """Drop the explicit per-user grant and reset the effective cache.

    After removal, the user's access falls back to the group level if a
    matching group grant exists, otherwise to deny_all.
    """
    UserWarRoomAccess.query.filter(and_(
        UserWarRoomAccess.user_id == user_id,
        UserWarRoomAccess.war_room_id == war_room_id,
    )).delete()
    db.session.commit()

    effective = _recompute_effective_access_level(user_id, war_room_id)
    if effective is None:
        effective = WarRoomAccessLevel.deny_all.value
    set_war_room_effective_access_for_user(user_id, war_room_id, effective)


def ac_fast_check_user_has_war_room_access(user_id, war_room_id, expected_access_levels):
    """Return the user's access_level if it matches one of the expected
    levels, else None.

    Resolves the cached effective access; if nothing's cached, walks the
    precedence chain once and writes it back. Falls through to
    `server_administrator` so admins can always reach a war room
    without being explicitly added.
    """
    if not war_room_id:
        return None

    from app.iris_engine.access_control.utils import ac_get_effective_permissions_of_user
    from app.datamgmt.manage.manage_users_db import get_user

    user = get_user(user_id)
    if user is None:
        return None

    perms = ac_get_effective_permissions_of_user(user)
    if ac_flag_match_mask(perms, Permissions.server_administrator.value):
        # Admins always have full access. Skip the cache, skip the chain.
        return WarRoomAccessLevel.full_access.value

    access_level = _get_effective_access_level(user_id, war_room_id)
    if access_level is None:
        access_level = _recompute_effective_access_level(user_id, war_room_id)
        if access_level is not None:
            set_war_room_effective_access_for_user(user_id, war_room_id, access_level)

    if access_level is None:
        return None
    if ac_flag_match_mask(access_level, WarRoomAccessLevel.deny_all.value):
        return None

    for level in expected_access_levels:
        if ac_flag_match_mask(access_level, level.value):
            return access_level
    return None


def ac_get_fast_user_war_rooms_access(user_id):
    """Return the war_room_ids the user can read.

    Used by the war-room list endpoint to filter the query. Admins get
    every row in `war_room` (handled by the caller).
    """
    rows = (
        UserWarRoomEffectiveAccess.query
        .with_entities(UserWarRoomEffectiveAccess.war_room_id)
        .filter(and_(
            UserWarRoomEffectiveAccess.user_id == user_id,
            UserWarRoomEffectiveAccess.access_level != WarRoomAccessLevel.deny_all.value,
        ))
        .all()
    )
    return [r.war_room_id for r in rows]
