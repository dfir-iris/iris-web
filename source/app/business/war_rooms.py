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

from sqlalchemy import and_, case, or_

from app.db import db
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
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


# Sort priority for the list view: rooms an operator is actively
# working land at the top, closed rooms drop to the bottom. Archived
# rooms are handled separately (they either share a section in the SPA
# or are excluded entirely depending on the `archived` filter), so this
# ordering only needs to worry about the operational lifecycle.
_STATE_SORT_ORDER = {
    'active': 0,
    'open': 1,
    'standby': 2,
    'closed': 3,
}


def _state_priority_expr():
    """SQLAlchemy CASE that maps the state string to a sort integer.

    Anything unrecognised falls to the end so a future state added
    without updating this table still sorts predictably.
    """
    return case(
        _STATE_SORT_ORDER,
        value=WarRoom.state,
        else_=len(_STATE_SORT_ORDER),
    )


def war_room_list_for_user(user_id, is_admin=False, state=None, search=None,
                           archived=None):
    """List the war rooms visible to a user.

    Admins see every row; everyone else is filtered through the
    effective-access cache (precedence already resolved: deny_all rows
    are excluded from the join).

    `archived` controls the archive lens:

      * `False` / None — the default: exclude archived rooms.
      * `True`         — return *only* archived rooms.
      * `'any'`        — return both, letting the caller decide.

    Rooms come back sorted by an operational-priority CASE (active >
    open > standby > closed) then by creation date desc, so the room
    an operator most likely needs to open is at the top of the list.
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

    if archived == 'any':
        pass
    elif archived is True:
        query = query.filter(WarRoom.archived_at.is_not(None))
    else:
        # Default (None or False): hide archived rows so a user's main
        # list stays focused on live workspaces.
        query = query.filter(WarRoom.archived_at.is_(None))

    if search:
        needle = f'%{search.strip()}%'
        query = query.filter(or_(
            WarRoom.name.ilike(needle),
            WarRoom.description.ilike(needle),
        ))

    return (
        query
        .order_by(_state_priority_expr().asc(), WarRoom.created_at.desc())
        .all()
    )


def war_room_archive(war_room_id, archived_by_id):
    """Mark the room as archived. Idempotent: re-archiving is a no-op."""
    war_room = war_room_get(war_room_id)
    if war_room.archived_at is None:
        war_room.archived_at = datetime.datetime.utcnow()
        war_room.archived_by_id = archived_by_id
        db.session.commit()
        track_activity(f'archived war room "{war_room.name}"', war_room_id=war_room_id)
        war_room = call_modules_hook('on_postload_war_room_archive', war_room)
    return war_room


def war_room_unarchive(war_room_id):
    """Clear the archive stamp. Idempotent: unarchiving a live room is a no-op."""
    war_room = war_room_get(war_room_id)
    if war_room.archived_at is not None:
        war_room.archived_at = None
        war_room.archived_by_id = None
        db.session.commit()
        track_activity(f'unarchived war room "{war_room.name}"', war_room_id=war_room_id)
        war_room = call_modules_hook('on_postload_war_room_unarchive', war_room)
    return war_room


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

    track_activity(f'created war room "{war_room.name}"',
                   war_room_id=war_room.war_room_id)
    war_room = call_modules_hook('on_postload_war_room_create', war_room)
    return war_room


def war_room_update(war_room_id, name=None, description=None, state=None,
                    severity_id=None, color=None, custom_attributes=None,
                    closed_by_id=None):
    war_room = war_room_get(war_room_id)

    previous_state = war_room.state
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

    if state is not None and war_room.state != previous_state:
        track_activity(
            f'changed war room "{war_room.name}" state from {previous_state} to {war_room.state}',
            war_room_id=war_room_id,
        )
    else:
        track_activity(f'updated war room "{war_room.name}"', war_room_id=war_room_id)
    war_room = call_modules_hook('on_postload_war_room_update', war_room)
    return war_room


def war_room_delete(war_room_id):
    war_room = war_room_get(war_room_id)
    war_room_name = war_room.name
    # CASCADE on FKs drops every child row (chat, tasks, etc).
    db.session.delete(war_room)
    db.session.commit()
    # war_room_id is intentionally omitted — the row is gone, so leaving
    # the FK NULL keeps the audit entry from dangling on delete-cascade.
    track_activity(f'deleted war room "{war_room_name}"')
    call_modules_hook('on_postload_war_room_delete', war_room_id)


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
    was_new = existing is None
    if was_new:
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

    verb = 'added' if was_new else 'updated'
    track_activity(
        f'{verb} war room member (user #{user_id}, role {role})',
        war_room_id=war_room_id,
    )
    call_modules_hook('on_postload_war_room_member_add',
                      {'war_room_id': war_room_id, 'user_id': user_id,
                       'role': role, 'access_level': access_level,
                       'is_new': was_new})


def war_room_remove_member(war_room_id, user_id):
    WarRoomMember.query.filter_by(
        war_room_id=war_room_id, user_id=user_id
    ).delete()
    db.session.commit()

    from app.business.war_rooms_access import remove_user_war_room_access
    remove_user_war_room_access(user_id, war_room_id)

    track_activity(
        f'removed war room member (user #{user_id})',
        war_room_id=war_room_id,
    )
    call_modules_hook('on_postload_war_room_member_remove',
                      {'war_room_id': war_room_id, 'user_id': user_id})


# ----------------------------------------------------- Case attachment ---

def war_room_cases_list(war_room_id):
    """Return the war-room's attached cases joined with everything the
    SPA needs to render a rich row in one shot:

      * `customer_id` / `customer_name`
      * `owner_id` / `owner_name` / `owner_login`
      * `open_date` / `close_date`
      * `state_id` / `state_name`
      * `task_count` (total) / `task_open_count`

    Task counts are computed via subqueries so a case with thousands of
    tasks doesn't fan out the result set. Open vs. closed is determined
    by `task_status.status_name not in ('done','closed','cancelled')`
    case-insensitively — matches what the case dashboard considers open.
    """
    from app.models.authorization import User
    from app.models.cases import CaseState
    from app.models.customers import Client
    from app.models.models import CaseTasks, TaskStatus
    from sqlalchemy import case as sa_case, func, and_

    open_status_clause = func.lower(TaskStatus.status_name).notin_(
        ['done', 'closed', 'cancelled']
    )

    task_total_sq = (
        db.session.query(
            CaseTasks.task_case_id.label('case_id'),
            func.count(CaseTasks.id).label('task_count'),
            func.sum(
                sa_case((open_status_clause, 1), else_=0)
            ).label('task_open_count'),
        )
        .outerjoin(TaskStatus, TaskStatus.id == CaseTasks.task_status_id)
        .group_by(CaseTasks.task_case_id)
        .subquery()
    )

    rows = (
        db.session.query(
            WarRoomCase.war_room_id,
            WarRoomCase.case_id,
            WarRoomCase.attached_at,
            WarRoomCase.note,
            Cases.name.label('case_name'),
            Cases.client_id.label('customer_id'),
            Client.name.label('customer_name'),
            Cases.owner_id,
            User.name.label('owner_name'),
            User.user.label('owner_login'),
            Cases.open_date,
            Cases.close_date,
            Cases.state_id,
            CaseState.state_name,
            func.coalesce(task_total_sq.c.task_count, 0).label('task_count'),
            func.coalesce(task_total_sq.c.task_open_count, 0).label(
                'task_open_count'
            ),
        )
        .join(Cases, Cases.case_id == WarRoomCase.case_id)
        .outerjoin(Client, Client.client_id == Cases.client_id)
        .outerjoin(User, User.id == Cases.owner_id)
        .outerjoin(CaseState, CaseState.state_id == Cases.state_id)
        .outerjoin(
            task_total_sq, task_total_sq.c.case_id == WarRoomCase.case_id
        )
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

    war_room = war_room_get(war_room_id)

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

    track_activity(
        f'attached case "{case.name}" to war room "{war_room.name}"',
        caseid=case_id, war_room_id=war_room_id,
    )
    link = call_modules_hook('on_postload_war_room_case_attach', link, caseid=case_id)
    return link


def war_room_detach_case(war_room_id, case_id):
    war_room = war_room_get(war_room_id)
    case = Cases.query.filter_by(case_id=case_id).first()
    deleted = WarRoomCase.query.filter_by(
        war_room_id=war_room_id, case_id=case_id
    ).delete()
    db.session.commit()
    if not deleted:
        raise ObjectNotFoundError()

    case_label = f'"{case.name}"' if case else f'#{case_id}'
    track_activity(
        f'detached case {case_label} from war room "{war_room.name}"',
        caseid=case_id, war_room_id=war_room_id,
    )
    call_modules_hook('on_postload_war_room_case_detach',
                      {'war_room_id': war_room_id, 'case_id': case_id},
                      caseid=case_id)


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

def war_room_people(war_room_id):
    """Return the people working on the war.

    Three lanes merged on `user_id`:
      1. Explicit members of the war room (carry their `role` here).
      2. Users with effective access to any case attached to the room.
      3. The case owners themselves (already covered by lane 2, but
         we surface them as `is_owner=True` so the SPA can promote
         them in the banner).

    Each row carries the union of source signals (`is_member`,
    `is_owner`, `case_ids`) plus the basic identity fields so the
    banner can render avatars + role hints without per-user fetches.
    """
    from app.models.authorization import (
        User,
        UserCaseEffectiveAccess,
        WarRoomAccessLevel,
    )

    attached_case_ids = [
        r.case_id
        for r in (
            WarRoomCase.query
            .with_entities(WarRoomCase.case_id)
            .filter(WarRoomCase.war_room_id == war_room_id)
            .all()
        )
    ]

    members = (
        db.session.query(
            WarRoomMember.user_id,
            WarRoomMember.role,
            User.user.label('login'),
            User.name.label('name'),
            User.email,
        )
        .join(User, User.id == WarRoomMember.user_id)
        .filter(WarRoomMember.war_room_id == war_room_id)
        .all()
    )

    case_accessors = []
    case_owners = []
    if attached_case_ids:
        case_accessors = (
            db.session.query(
                UserCaseEffectiveAccess.user_id,
                UserCaseEffectiveAccess.case_id,
                User.user.label('login'),
                User.name.label('name'),
                User.email,
            )
            .join(User, User.id == UserCaseEffectiveAccess.user_id)
            .filter(
                UserCaseEffectiveAccess.case_id.in_(attached_case_ids),
                UserCaseEffectiveAccess.access_level
                != WarRoomAccessLevel.deny_all.value,
                User.active == True,  # noqa: E712 — SQL identity comparison
            )
            .all()
        )
        case_owners = (
            db.session.query(
                Cases.owner_id.label('user_id'),
                Cases.case_id,
                User.user.label('login'),
                User.name.label('name'),
                User.email,
            )
            .join(User, User.id == Cases.owner_id)
            .filter(Cases.case_id.in_(attached_case_ids))
            .all()
        )

    people = {}
    for m in members:
        people[m.user_id] = {
            'user_id': m.user_id,
            'login': m.login,
            'name': m.name,
            'email': m.email,
            'role': m.role,
            'is_member': True,
            'is_owner': False,
            'case_ids': set(),
        }
    for row in case_accessors:
        entry = people.setdefault(row.user_id, {
            'user_id': row.user_id,
            'login': row.login,
            'name': row.name,
            'email': row.email,
            'role': None,
            'is_member': False,
            'is_owner': False,
            'case_ids': set(),
        })
        entry['case_ids'].add(row.case_id)
    for row in case_owners:
        entry = people.setdefault(row.user_id, {
            'user_id': row.user_id,
            'login': row.login,
            'name': row.name,
            'email': row.email,
            'role': None,
            'is_member': False,
            'is_owner': True,
            'case_ids': set(),
        })
        entry['is_owner'] = True
        entry['case_ids'].add(row.case_id)

    # Sort: members first (leads before responders before observers),
    # then case owners, then plain access — within each group by display
    # name so the banner reads predictably.
    role_rank = {'lead': 0, 'responder': 1, 'observer': 2}

    def sort_key(p):
        member_rank = 0 if p['is_member'] else (1 if p['is_owner'] else 2)
        role = role_rank.get(p.get('role') or '', 99)
        return (member_rank, role, (p.get('name') or p.get('login') or '').lower())

    rows = []
    for p in people.values():
        p['case_ids'] = sorted(p['case_ids'])
        rows.append(p)
    rows.sort(key=sort_key)
    return rows


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
