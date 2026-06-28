#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""Business layer for war rooms.

Covers war-room CRUD, membership management, case attachment, default
timeline provisioning, and ACL bootstrap. Keeps the REST blueprints
thin and lets test code call straight into the business layer without
mocking Flask.
"""

import datetime
import re

from sqlalchemy import and_, or_

from app.db import db
from app.models.authorization import (
    GroupWarRoomAccess,
    UserWarRoomAccess,
    UserWarRoomEffectiveAccess,
    WarRoomAccessLevel,
)
from app.models.cases import Cases
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.war_rooms import (
    WarRoom,
    WarRoomCase,
    WarRoomMember,
    WarRoomMemberRole,
    WarRoomState,
    WarRoomTimeline,
)


_NAME_MAX_LEN = 256
_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
_VALID_STATES = {s.value for s in WarRoomState}
_VALID_ROLES = {r.value for r in WarRoomMemberRole}


def _validate_name(name):
    if not isinstance(name, str):
        raise BusinessProcessingError('War room name must be a string')
    stripped = name.strip()
    if not stripped:
        raise BusinessProcessingError('War room name is required')
    if len(stripped) > _NAME_MAX_LEN:
        raise BusinessProcessingError(
            f'War room name must be at most {_NAME_MAX_LEN} characters'
        )
    return stripped


def _validate_color(color):
    if color is None or color == '':
        return None
    if not isinstance(color, str) or not _HEX_COLOR_RE.match(color):
        raise BusinessProcessingError('Color must be a hex string like #RRGGBB')
    return color


def _validate_state(state):
    if state is None:
        return None
    if not isinstance(state, str) or state not in _VALID_STATES:
        raise BusinessProcessingError(
            f'State must be one of {", ".join(sorted(_VALID_STATES))}'
        )
    return state


def _validate_role(role):
    if role is None:
        return WarRoomMemberRole.responder.value
    if not isinstance(role, str) or role not in _VALID_ROLES:
        raise BusinessProcessingError(
            f'Role must be one of {", ".join(sorted(_VALID_ROLES))}'
        )
    return role


def war_room_exists(war_room_id):
    return db.session.query(
        WarRoom.query.filter_by(war_room_id=war_room_id).exists()
    ).scalar()


def war_room_get(war_room_id):
    row = WarRoom.query.filter_by(war_room_id=war_room_id).first()
    if row is None:
        raise ObjectNotFoundError()
    return row


def war_room_list_for_user(user_id, is_admin=False, state=None, search=None):
    """List the war rooms visible to a user.

    Admins see every row; everyone else is filtered through the
    effective-access cache (precedence already resolved: deny_all rows
    are excluded from the join).
    """
    query = WarRoom.query
    if not is_admin:
        query = (
            query
            .join(UserWarRoomEffectiveAccess,
                  UserWarRoomEffectiveAccess.war_room_id == WarRoom.war_room_id)
            .filter(and_(
                UserWarRoomEffectiveAccess.user_id == user_id,
                UserWarRoomEffectiveAccess.access_level != WarRoomAccessLevel.deny_all.value,
            ))
        )

    if state is not None:
        state = _validate_state(state)
        query = query.filter(WarRoom.state == state)

    if search:
        needle = f'%{search.strip()}%'
        query = query.filter(or_(
            WarRoom.name.ilike(needle),
            WarRoom.description.ilike(needle),
        ))

    return query.order_by(WarRoom.created_at.desc()).all()


def war_room_create(name, description=None, state=None, severity_id=None,
                    color=None, created_by_id=None, custom_attributes=None):
    name = _validate_name(name)
    color = _validate_color(color)
    state = _validate_state(state) or WarRoomState.open.value

    war_room = WarRoom()
    war_room.name = name
    war_room.description = description
    war_room.state = state
    war_room.severity_id = severity_id
    war_room.color = color
    war_room.created_by_id = created_by_id
    war_room.custom_attributes = custom_attributes
    db.session.add(war_room)
    db.session.commit()

    # Bootstrap: creator becomes a lead member with full access.
    if created_by_id is not None:
        member = WarRoomMember()
        member.war_room_id = war_room.war_room_id
        member.user_id = created_by_id
        member.role = WarRoomMemberRole.lead.value
        member.added_by_id = created_by_id
        db.session.add(member)
        db.session.commit()

        from app.business.war_rooms_access import set_user_war_room_access
        set_user_war_room_access(
            created_by_id, war_room.war_room_id,
            WarRoomAccessLevel.full_access.value
        )

    # Every war room ships with a Main timeline so the SPA's sidebar has
    # something to land on even before the operator creates more.
    war_room_ensure_default_timeline(war_room.war_room_id,
                                     created_by_id=created_by_id)

    return war_room


def war_room_update(war_room_id, name=None, description=None, state=None,
                    severity_id=None, color=None, custom_attributes=None,
                    closed_by_id=None):
    war_room = war_room_get(war_room_id)

    if name is not None:
        war_room.name = _validate_name(name)
    if description is not None:
        war_room.description = description
    if state is not None:
        new_state = _validate_state(state)
        # State transition to / from closed flips the closed_at stamp so
        # the dashboard can report MTTR-style metrics.
        if new_state == WarRoomState.closed.value and war_room.state != WarRoomState.closed.value:
            war_room.closed_at = datetime.datetime.utcnow()
            war_room.closed_by_id = closed_by_id
        elif new_state != WarRoomState.closed.value and war_room.state == WarRoomState.closed.value:
            war_room.closed_at = None
            war_room.closed_by_id = None
        war_room.state = new_state
    if severity_id is not None:
        war_room.severity_id = severity_id
    if color is not None:
        war_room.color = _validate_color(color)
    if custom_attributes is not None:
        war_room.custom_attributes = custom_attributes

    db.session.commit()
    return war_room


def war_room_delete(war_room_id):
    war_room = war_room_get(war_room_id)
    # CASCADE on FKs drops every child row (chat, tasks, etc).
    db.session.delete(war_room)
    db.session.commit()


# ------------------------------------------------------------ Members ----

def war_room_members_list(war_room_id):
    from app.models.authorization import User
    rows = (
        db.session.query(
            WarRoomMember.war_room_id,
            WarRoomMember.user_id,
            WarRoomMember.role,
            WarRoomMember.added_at,
            User.user.label('login'),
            User.name.label('name'),
        )
        .join(User, User.id == WarRoomMember.user_id)
        .filter(WarRoomMember.war_room_id == war_room_id)
        .order_by(WarRoomMember.added_at.asc())
        .all()
    )
    return rows


def war_room_add_member(war_room_id, user_id, role=None, added_by_id=None,
                        access_level=None):
    """Add a member and grant them ACL access in one transaction.

    `access_level` defaults to `full_access` — observers can be added
    with `read_only` explicitly. Idempotent: re-adding a member updates
    their role + ACL level instead of raising.
    """
    role = _validate_role(role)
    if access_level is None:
        access_level = WarRoomAccessLevel.full_access.value
    if access_level not in (level.value for level in WarRoomAccessLevel):
        raise BusinessProcessingError('Invalid access_level')

    existing = WarRoomMember.query.filter_by(
        war_room_id=war_room_id, user_id=user_id
    ).first()
    if existing is None:
        member = WarRoomMember()
        member.war_room_id = war_room_id
        member.user_id = user_id
        member.role = role
        member.added_by_id = added_by_id
        db.session.add(member)
    else:
        existing.role = role
    db.session.commit()

    from app.business.war_rooms_access import set_user_war_room_access
    set_user_war_room_access(user_id, war_room_id, access_level)


def war_room_remove_member(war_room_id, user_id):
    WarRoomMember.query.filter_by(
        war_room_id=war_room_id, user_id=user_id
    ).delete()
    db.session.commit()

    from app.business.war_rooms_access import remove_user_war_room_access
    remove_user_war_room_access(user_id, war_room_id)


# ----------------------------------------------------- Case attachment ---

def war_room_cases_list(war_room_id):
    """Return the war-room's attached cases joined with their customer.

    Customer name is denormalised onto the row so the SPA can render
    it without a per-row fetch. `customer_id` and `customer_name`
    might be NULL on truly orphan cases (shouldn't happen — `Cases`
    has a non-null FK to `Client` — but the LEFT OUTER JOIN keeps
    the listing robust against bad data).
    """
    from app.models.customers import Client

    rows = (
        db.session.query(
            WarRoomCase.war_room_id,
            WarRoomCase.case_id,
            WarRoomCase.attached_at,
            WarRoomCase.note,
            Cases.name.label('case_name'),
            Cases.client_id.label('customer_id'),
            Client.name.label('customer_name'),
        )
        .join(Cases, Cases.case_id == WarRoomCase.case_id)
        .outerjoin(Client, Client.client_id == Cases.client_id)
        .filter(WarRoomCase.war_room_id == war_room_id)
        .order_by(WarRoomCase.attached_at.asc())
        .all()
    )
    return rows


def war_room_attach_case(war_room_id, case_id, attached_by_id=None, note=None):
    """Attach a case to a war room.

    The REST layer must validate that the actor has `full_access` on
    the case *before* calling this — this layer trusts that gate and
    only enforces the war-room write level.
    """
    case = Cases.query.filter_by(case_id=case_id).first()
    if case is None:
        raise BusinessProcessingError('Case not found')

    existing = WarRoomCase.query.filter_by(
        war_room_id=war_room_id, case_id=case_id
    ).first()
    if existing is not None:
        # Idempotent: refresh the note + bump attached_at if provided.
        if note is not None:
            existing.note = note
        db.session.commit()
        return existing

    link = WarRoomCase()
    link.war_room_id = war_room_id
    link.case_id = case_id
    link.attached_by_id = attached_by_id
    link.note = note
    db.session.add(link)
    db.session.commit()
    return link


def war_room_detach_case(war_room_id, case_id):
    deleted = WarRoomCase.query.filter_by(
        war_room_id=war_room_id, case_id=case_id
    ).delete()
    db.session.commit()
    if not deleted:
        raise ObjectNotFoundError()


def war_rooms_for_case(case_id):
    """Return the war rooms a case is currently attached to.

    Used by the case detail page to render the "in war room" badge.
    """
    rows = (
        db.session.query(
            WarRoom.war_room_id,
            WarRoom.name,
            WarRoom.state,
            WarRoom.color,
        )
        .join(WarRoomCase, WarRoomCase.war_room_id == WarRoom.war_room_id)
        .filter(WarRoomCase.case_id == case_id)
        .order_by(WarRoom.created_at.desc())
        .all()
    )
    return rows


# --------------------------------------------- Default timeline guarantee

def war_room_ensure_default_timeline(war_room_id, created_by_id=None):
    """Create the war room's "Main" timeline if missing. Idempotent."""
    existing = (
        WarRoomTimeline.query
        .filter_by(war_room_id=war_room_id, is_default=True)
        .first()
    )
    if existing is not None:
        return existing

    timeline = WarRoomTimeline()
    timeline.war_room_id = war_room_id
    timeline.name = 'Main'
    timeline.description = 'Default war-room timeline'
    timeline.is_default = True
    timeline.created_by_id = created_by_id
    db.session.add(timeline)
    db.session.commit()
    return timeline
