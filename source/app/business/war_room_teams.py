#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""Business layer for per-war-room teams.

Teams are named groupings of war-room members used as @-mention
targets in chat, threads, notes, and tasks. Team scope is the war room:
name uniqueness, membership add/remove, and cascade delete all key off
`war_room_id`.
"""

import re

from app.db import db
from app.iris_engine.utils.tracker import track_activity
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.war_rooms import (
    WarRoomMember,
    WarRoomTeam,
    WarRoomTeamMember,
)


_NAME_MAX_LEN = 80
_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def _validate_name(name):
    if not isinstance(name, str):
        raise BusinessProcessingError('Team name must be a string')
    stripped = name.strip()
    if not stripped:
        raise BusinessProcessingError('Team name is required')
    if len(stripped) > _NAME_MAX_LEN:
        raise BusinessProcessingError(
            f'Team name must be at most {_NAME_MAX_LEN} characters'
        )
    return stripped


def _validate_color(color):
    if color is None or color == '':
        return None
    if not isinstance(color, str) or not _HEX_COLOR_RE.match(color):
        raise BusinessProcessingError('Color must be a hex string like #RRGGBB')
    return color


def war_room_team_list(war_room_id):
    return (
        WarRoomTeam.query
        .filter(WarRoomTeam.war_room_id == war_room_id)
        .order_by(WarRoomTeam.name.asc())
        .all()
    )


def war_room_team_get(war_room_id, team_id):
    team = (
        WarRoomTeam.query
        .filter(WarRoomTeam.war_room_id == war_room_id)
        .filter(WarRoomTeam.team_id == team_id)
        .first()
    )
    if team is None:
        raise ObjectNotFoundError('Team not found')
    return team


def war_room_team_create(war_room_id, name, description=None, color=None,
                         created_by_id=None):
    name = _validate_name(name)
    color = _validate_color(color)

    existing = (
        WarRoomTeam.query
        .filter(WarRoomTeam.war_room_id == war_room_id)
        .filter(WarRoomTeam.name == name)
        .first()
    )
    if existing is not None:
        raise BusinessProcessingError('A team with that name already exists')

    team = WarRoomTeam(
        war_room_id=war_room_id,
        name=name,
        description=(description or None),
        color=color,
        created_by_id=created_by_id,
    )
    db.session.add(team)
    db.session.commit()
    track_activity(
        f'Created war-room team "{team.name}"',
        user_input=False,
    )
    return team


def war_room_team_update(war_room_id, team_id, name=None, description=None,
                         color=None):
    team = war_room_team_get(war_room_id, team_id)

    if name is not None:
        new_name = _validate_name(name)
        if new_name != team.name:
            collision = (
                WarRoomTeam.query
                .filter(WarRoomTeam.war_room_id == war_room_id)
                .filter(WarRoomTeam.name == new_name)
                .filter(WarRoomTeam.team_id != team_id)
                .first()
            )
            if collision is not None:
                raise BusinessProcessingError('A team with that name already exists')
            team.name = new_name

    if description is not None:
        team.description = description or None

    if color is not None:
        team.color = _validate_color(color)

    db.session.commit()
    return team


def war_room_team_delete(war_room_id, team_id):
    team = war_room_team_get(war_room_id, team_id)
    db.session.delete(team)
    db.session.commit()


def war_room_team_members_list(war_room_id, team_id):
    # Validate scope: team must belong to this war room.
    war_room_team_get(war_room_id, team_id)
    return (
        WarRoomTeamMember.query
        .filter(WarRoomTeamMember.team_id == team_id)
        .all()
    )


def war_room_team_member_add(war_room_id, team_id, user_id, added_by_id=None):
    """Add a user to a team; auto-add them to the war room if needed.

    A user who isn't a `WarRoomMember` of this room gets added as
    `responder` with `full_access` first, then joined to the team.
    Same transaction envelope as the pure team-add path.

    Returns a `(row, auto_added_as_room_member)` tuple so the API layer
    can echo "user was also added to the war room as responder" back to
    the caller.
    """
    war_room_team_get(war_room_id, team_id)

    if not isinstance(user_id, int):
        raise BusinessProcessingError('user_id is required')

    # Auto-provision war-room membership if missing. This keeps the
    # invariant that every team member is also a room member — the
    # CASCADE on WarRoomTeamMember.user_id still cleans up if the user
    # is later removed from the room.
    room_member = (
        WarRoomMember.query
        .filter(WarRoomMember.war_room_id == war_room_id)
        .filter(WarRoomMember.user_id == user_id)
        .first()
    )
    auto_added_room_member = False
    if room_member is None:
        # Local import to avoid a module-load import loop:
        # war_rooms → war_rooms_access → (already loaded), and this
        # module is imported by REST init, which happens before
        # war_rooms in some test paths.
        from app.business.war_rooms import war_room_add_member
        war_room_add_member(
            war_room_id, user_id,
            role='responder',
            added_by_id=added_by_id,
        )
        auto_added_room_member = True

    existing = (
        WarRoomTeamMember.query
        .filter(WarRoomTeamMember.team_id == team_id)
        .filter(WarRoomTeamMember.user_id == user_id)
        .first()
    )
    if existing is not None:
        return existing, auto_added_room_member

    row = WarRoomTeamMember(
        team_id=team_id,
        user_id=user_id,
        added_by_id=added_by_id,
    )
    db.session.add(row)
    db.session.commit()
    return row, auto_added_room_member


def war_room_team_member_remove(war_room_id, team_id, user_id):
    war_room_team_get(war_room_id, team_id)
    row = (
        WarRoomTeamMember.query
        .filter(WarRoomTeamMember.team_id == team_id)
        .filter(WarRoomTeamMember.user_id == user_id)
        .first()
    )
    if row is None:
        raise ObjectNotFoundError('Team member not found')
    db.session.delete(row)
    db.session.commit()


def war_room_team_member_user_ids(war_room_id, team_ids):
    """Return the union of `user_id`s across the given teams.

    Used by the notification pipeline to expand a set of @-team mentions
    into the set of users to notify. Teams outside the given war room
    are silently ignored — a scope leak here would notify people who
    can't read the source content.
    """
    if not team_ids:
        return set()
    rows = (
        db.session.query(WarRoomTeamMember.user_id)
        .join(WarRoomTeam, WarRoomTeam.team_id == WarRoomTeamMember.team_id)
        .filter(WarRoomTeam.war_room_id == war_room_id)
        .filter(WarRoomTeam.team_id.in_(list(team_ids)))
        .all()
    )
    return {r.user_id for r in rows}
