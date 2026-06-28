#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Business layer for war-room tasks.

Mirrors `case_tasks` but scoped to a war room. A war-room task can
optionally point at a source case (and a source case task) so the
operator can promote a per-case task into a war-room-level
coordination item without losing the link.
"""

import datetime

from app.db import db
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.war_rooms import WarRoomTask


_TITLE_MAX_LEN = 1024


def _validate_title(title):
    if not isinstance(title, str):
        raise BusinessProcessingError('Task title must be a string')
    stripped = title.strip()
    if not stripped:
        raise BusinessProcessingError('Task title is required')
    if len(stripped) > _TITLE_MAX_LEN:
        raise BusinessProcessingError(
            f'Task title must be at most {_TITLE_MAX_LEN} characters'
        )
    return stripped


def war_room_task_list(war_room_id):
    """List tasks on a war room with assignee / creator / closer joined.

    Three independent outer-joins on `User` (aliased) so a single row
    carries the display name for every actor — the SPA shows them as
    "<assignee> · created by <creator>" without a per-row roundtrip.
    """
    from app.models.authorization import User
    from sqlalchemy.orm import aliased

    Assignee = aliased(User)
    Creator = aliased(User)
    Closer = aliased(User)

    rows = (
        db.session.query(
            WarRoomTask.task_id,
            WarRoomTask.war_room_id,
            WarRoomTask.title,
            WarRoomTask.description,
            WarRoomTask.status_id,
            WarRoomTask.assignee_id,
            WarRoomTask.due_at,
            WarRoomTask.source_case_id,
            WarRoomTask.source_case_task_id,
            WarRoomTask.created_at,
            WarRoomTask.created_by_id,
            WarRoomTask.closed_at,
            WarRoomTask.closed_by_id,
            WarRoomTask.tags,
            Assignee.user.label('assignee_login'),
            Assignee.name.label('assignee_name'),
            Creator.user.label('created_by_login'),
            Creator.name.label('created_by_name'),
            Closer.user.label('closed_by_login'),
            Closer.name.label('closed_by_name'),
        )
        .outerjoin(Assignee, Assignee.id == WarRoomTask.assignee_id)
        .outerjoin(Creator, Creator.id == WarRoomTask.created_by_id)
        .outerjoin(Closer, Closer.id == WarRoomTask.closed_by_id)
        .filter(WarRoomTask.war_room_id == war_room_id)
        .order_by(WarRoomTask.created_at.desc())
        .all()
    )
    return rows


def war_room_task_get(war_room_id, task_id):
    row = WarRoomTask.query.filter_by(
        war_room_id=war_room_id, task_id=task_id
    ).first()
    if row is None:
        raise ObjectNotFoundError()
    return row


def war_room_task_create(war_room_id, title, description=None,
                         status_id=None, assignee_id=None, due_at=None,
                         source_case_id=None, source_case_task_id=None,
                         tags=None, created_by_id=None):
    title = _validate_title(title)
    task = WarRoomTask()
    task.war_room_id = war_room_id
    task.title = title
    task.description = description
    task.status_id = status_id
    task.assignee_id = assignee_id
    task.due_at = due_at
    task.source_case_id = source_case_id
    task.source_case_task_id = source_case_task_id
    task.tags = tags
    task.created_by_id = created_by_id
    db.session.add(task)
    db.session.commit()
    return task


def war_room_task_update(war_room_id, task_id, **fields):
    task = war_room_task_get(war_room_id, task_id)
    if 'title' in fields and fields['title'] is not None:
        task.title = _validate_title(fields['title'])
    for f in ('description', 'status_id', 'assignee_id', 'due_at',
              'source_case_id', 'source_case_task_id', 'tags'):
        if f in fields:
            setattr(task, f, fields[f])
    db.session.commit()
    return task


def war_room_task_close(war_room_id, task_id, closed_by_id=None):
    task = war_room_task_get(war_room_id, task_id)
    task.closed_at = datetime.datetime.utcnow()
    task.closed_by_id = closed_by_id
    db.session.commit()
    return task


def war_room_task_reopen(war_room_id, task_id):
    task = war_room_task_get(war_room_id, task_id)
    task.closed_at = None
    task.closed_by_id = None
    db.session.commit()
    return task


def war_room_task_delete(war_room_id, task_id):
    task = war_room_task_get(war_room_id, task_id)
    db.session.delete(task)
    db.session.commit()
