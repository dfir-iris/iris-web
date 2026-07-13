#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Business layer for war-room tasks.

Mirrors `case_tasks` but scoped to a war room. A war-room task can
optionally point at a source case (and a source case task) so the
operator can promote a per-case task into a war-room-level
coordination item without losing the link.

Task management extensions (subtasks, status via task_status, tags,
search): parents can have children but children cannot; the tags
column is free-form comma-separated to match the rest of Iris; the
status column reuses the shared `task_status` taxonomy.
"""

import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import aliased

from app.db import db
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.war_rooms import WarRoomTask


_TITLE_MAX_LEN = 1024


# Cache for the once-per-process check of whether the `parent_task_id`
# column exists on the live database. Same rolling-upgrade rationale
# as `_threads_supported` in war_room_chat: an install that hasn't
# applied the subtasks migration should still be able to render the
# tasks page; subtasks features just go dark until the migration
# lands.
_SUBTASKS_SUPPORTED = None


def _subtasks_supported():
    global _SUBTASKS_SUPPORTED
    if _SUBTASKS_SUPPORTED is True:
        return True
    try:
        from sqlalchemy import text as _text
        with db.engine.connect() as conn:
            conn.execute(
                _text('SELECT parent_task_id FROM war_room_task LIMIT 0')
            )
        supported = True
    except Exception as e:
        from app.logger import logger
        pgcode = getattr(getattr(e, 'orig', None), 'pgcode', None)
        if pgcode == '42703':
            logger.info('Subtasks disabled: parent_task_id column missing')
        else:
            logger.exception(
                'Subtasks support probe failed unexpectedly (pgcode=%s)',
                pgcode,
            )
        return False
    if supported:
        _SUBTASKS_SUPPORTED = True
    return supported


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


def _normalize_tags(tags):
    """Trim + de-duplicate a comma-separated tag string.

    Accepts either a list or a comma-separated string; always returns
    a comma-separated string (or None if empty). Preserves user order
    on the first occurrence of each tag.
    """
    if tags is None:
        return None
    if isinstance(tags, list):
        items = tags
    elif isinstance(tags, str):
        items = tags.split(',')
    else:
        raise BusinessProcessingError('tags must be a string or list')
    seen = set()
    out = []
    for raw in items:
        if not isinstance(raw, str):
            continue
        t = raw.strip()
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return ','.join(out) if out else None


def _base_task_query(war_room_id):
    """Build the joined-row query used by list/get-with-actors.

    Three independent outer-joins on `User` (aliased) so a single row
    carries the display name for every actor. Also joins `TaskStatus`
    so the SPA can render the status pill without a per-row lookup.
    """
    from app.models.authorization import User
    from app.models.models import TaskStatus

    Assignee = aliased(User)
    Creator = aliased(User)
    Closer = aliased(User)

    columns = [
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
        TaskStatus.status_name.label('status_name'),
        TaskStatus.status_bscolor.label('status_bscolor'),
    ]
    # parent_task_id is only exposed if the migration has landed; on
    # pre-migration DBs we return NULL so downstream serialisers see
    # a consistent shape.
    if _subtasks_supported():
        columns.append(WarRoomTask.parent_task_id.label('parent_task_id'))

    q = (
        db.session.query(*columns)
        .outerjoin(Assignee, Assignee.id == WarRoomTask.assignee_id)
        .outerjoin(Creator, Creator.id == WarRoomTask.created_by_id)
        .outerjoin(Closer, Closer.id == WarRoomTask.closed_by_id)
        .outerjoin(TaskStatus, TaskStatus.id == WarRoomTask.status_id)
        .filter(WarRoomTask.war_room_id == war_room_id)
    )
    return q


def war_room_task_list(war_room_id, q=None, status_ids=None, tags=None,
                       assignee_ids=None, parent_task_id=None,
                       due_from=None, due_to=None, include_no_due=True,
                       include_closed=True, page=None, per_page=None):
    """List tasks with optional search + filters.

    All filters are AND-combined. `q` matches title or description
    case-insensitively. `tags` is a list of tag strings; a task matches
    if any of its comma-separated tags matches (case-insensitive
    substring on the CSV, bracketed by commas so "foo" doesn't match
    "foobar"). `assignee_ids` can include `0` to mean Unassigned.
    `parent_task_id`: pass `0`/`None` for top-level only via the flag
    on the REST layer — this helper simply forwards the value; use
    `-1` to include everything (no parent filter).

    Pagination: when `page` is provided, return a dict envelope with
    `total`, `data`, `last_page`, `current_page`, `next_page`. When
    `page` is None, return the raw row list (back-compat for callers
    that want everything at once).

    Due-date filter semantics: rows are kept if their `due_at` falls
    within `[due_from, due_to]` (either endpoint may be None to make
    that side open-ended). Rows with no due date are kept when
    `include_no_due=True`, so a filter like "due this week" doesn't
    silently drop the untriaged backlog.
    """
    query = _base_task_query(war_room_id)

    if q:
        needle = f'%{q.strip().lower()}%'
        query = query.filter(or_(
            func.lower(WarRoomTask.title).like(needle),
            func.lower(func.coalesce(WarRoomTask.description, '')).like(needle),
        ))

    if status_ids:
        query = query.filter(WarRoomTask.status_id.in_(status_ids))

    if assignee_ids:
        conds = []
        real_ids = [aid for aid in assignee_ids if aid and aid != 0]
        if 0 in assignee_ids or None in assignee_ids:
            conds.append(WarRoomTask.assignee_id.is_(None))
        if real_ids:
            conds.append(WarRoomTask.assignee_id.in_(real_ids))
        if conds:
            query = query.filter(or_(*conds))

    if tags:
        tag_conds = []
        # Match whole-tag: bracket the CSV with commas so the needle
        # ",foo," can't match a substring of ",foobar,". Portable
        # across Postgres via `func.concat`.
        tag_expr = func.lower(
            func.concat(',', func.coalesce(WarRoomTask.tags, ''), ',')
        )
        for t in tags:
            if not isinstance(t, str) or not t.strip():
                continue
            needle = f'%,{t.strip().lower()},%'
            tag_conds.append(tag_expr.like(needle))
        if tag_conds:
            query = query.filter(or_(*tag_conds))

    if parent_task_id is not None and parent_task_id != -1:
        if parent_task_id == 0 and _subtasks_supported():
            query = query.filter(WarRoomTask.parent_task_id.is_(None))
        elif _subtasks_supported():
            query = query.filter(
                WarRoomTask.parent_task_id == parent_task_id
            )

    if due_from is not None or due_to is not None:
        range_conds = []
        if due_from is not None and due_to is not None:
            range_conds.append(WarRoomTask.due_at.between(due_from, due_to))
        elif due_from is not None:
            range_conds.append(WarRoomTask.due_at >= due_from)
        else:
            range_conds.append(WarRoomTask.due_at <= due_to)
        if include_no_due:
            range_conds.append(WarRoomTask.due_at.is_(None))
        query = query.filter(or_(*range_conds))

    if not include_closed:
        query = query.filter(WarRoomTask.closed_at.is_(None))

    query = query.order_by(WarRoomTask.created_at.desc())

    if page is None:
        return query.all()

    per_page = max(1, min(int(per_page or 25), 200))
    page = max(1, int(page))
    total = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    last_page = max(1, (total + per_page - 1) // per_page)
    next_page = page + 1 if page < last_page else None
    return {
        'total': total,
        'data': rows,
        'last_page': last_page,
        'current_page': page,
        'next_page': next_page,
    }


def war_room_task_get(war_room_id, task_id):
    row = WarRoomTask.query.filter_by(
        war_room_id=war_room_id, task_id=task_id
    ).first()
    if row is None:
        raise ObjectNotFoundError()
    return row


def _resolve_parent(war_room_id, parent_task_id):
    """Fetch + validate a candidate parent task.

    A parent must (1) exist, (2) live in the same war room, and
    (3) not itself be a subtask (single-level tree). Returns the
    parent row or raises BusinessProcessingError.
    """
    if parent_task_id is None:
        return None
    if not _subtasks_supported():
        raise BusinessProcessingError(
            'Subtasks are not available on this database yet'
        )
    parent = WarRoomTask.query.filter_by(
        war_room_id=war_room_id, task_id=parent_task_id
    ).first()
    if parent is None:
        raise BusinessProcessingError('Parent task not found')
    if parent.parent_task_id is not None:
        raise BusinessProcessingError(
            'Cannot nest subtasks more than one level deep'
        )
    return parent


def _fire_mention_notifications(task, actor_id, is_update):
    """Notify war-room members mentioned in a task's title or description.

    Silent on failure — a broken notification pipeline must not fail a
    task write.
    """
    try:
        from app.iris_engine.notifications.mentions import resolve_mentions_to_user_ids
        from app.iris_engine.notifications.service import notify_many
        from app.models.war_rooms import WarRoomMember

        # Mentions in either the title or the body — description carries
        # the TipTap HTML for the mention span; title is plain text but
        # extract works safely on either (yields empty set for pure text).
        combined = ' '.join(filter(None, [task.title, task.description]))
        mentioned = resolve_mentions_to_user_ids(combined, task.war_room_id)
        if not mentioned:
            return

        member_ids = {
            row.user_id for row in
            WarRoomMember.query
            .filter(WarRoomMember.war_room_id == task.war_room_id)
            .filter(WarRoomMember.user_id.in_(mentioned))
            .all()
        }
        if not member_ids:
            return

        verb = 'updated' if is_update else 'created'
        notify_many(
            user_ids=list(member_ids),
            event_type='mention',
            title=f'You were mentioned in a war-room task',
            body=f'{verb}: {task.title}',
            link=f'/war-rooms/{task.war_room_id}/tasks?task={task.task_id}',
            source_type='war_room_task',
            source_id=task.task_id,
            exclude_user_ids=[actor_id] if actor_id else [],
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            'war-room task mention notification failed')


def war_room_task_create(war_room_id, title, description=None,
                         status_id=None, assignee_id=None, due_at=None,
                         source_case_id=None, source_case_task_id=None,
                         tags=None, parent_task_id=None,
                         created_by_id=None):
    title = _validate_title(title)
    _resolve_parent(war_room_id, parent_task_id)
    task = WarRoomTask()
    task.war_room_id = war_room_id
    task.title = title
    task.description = description
    task.status_id = status_id
    task.assignee_id = assignee_id
    task.due_at = due_at
    task.source_case_id = source_case_id
    task.source_case_task_id = source_case_task_id
    task.tags = _normalize_tags(tags)
    task.created_by_id = created_by_id
    if _subtasks_supported():
        task.parent_task_id = parent_task_id
    db.session.add(task)
    db.session.commit()
    track_activity(f'created war room task "{task.title}"', war_room_id=war_room_id)
    _fire_mention_notifications(task, created_by_id, is_update=False)
    task = call_modules_hook('on_postload_war_room_task_create', task)
    return task


def war_room_task_update(war_room_id, task_id, **fields):
    # `updated_by_id` is metadata about the actor, not a column on the
    # task row. Pop it up front so the setattr loop below doesn't try
    # to write it back to the DB.
    updated_by_id = fields.pop('updated_by_id', None)
    task = war_room_task_get(war_room_id, task_id)
    prior_title = task.title
    prior_description = task.description
    if 'title' in fields and fields['title'] is not None:
        task.title = _validate_title(fields['title'])
    if 'parent_task_id' in fields:
        new_parent_id = fields.pop('parent_task_id')
        if new_parent_id == task.task_id:
            raise BusinessProcessingError('A task cannot be its own parent')
        if new_parent_id is not None and _subtasks_supported():
            # If this task already has subtasks, it cannot itself
            # become a child — that would break the single-level rule.
            has_children = db.session.query(
                WarRoomTask.query.filter_by(
                    parent_task_id=task.task_id
                ).exists()
            ).scalar()
            if has_children:
                raise BusinessProcessingError(
                    'Cannot demote a task with subtasks into a subtask'
                )
        _resolve_parent(war_room_id, new_parent_id)
        if _subtasks_supported():
            task.parent_task_id = new_parent_id
    for f in ('description', 'status_id', 'assignee_id', 'due_at',
              'source_case_id', 'source_case_task_id'):
        if f in fields:
            setattr(task, f, fields[f])
    if 'tags' in fields:
        task.tags = _normalize_tags(fields['tags'])
    db.session.commit()
    track_activity(f'updated war room task "{task.title}"', war_room_id=war_room_id)
    # Fire only when the mention-carrying fields changed.
    if task.title != prior_title or task.description != prior_description:
        _fire_mention_notifications(task, updated_by_id, is_update=True)
    task = call_modules_hook('on_postload_war_room_task_update', task)
    return task


def war_room_task_close(war_room_id, task_id, closed_by_id=None):
    task = war_room_task_get(war_room_id, task_id)
    task.closed_at = datetime.datetime.utcnow()
    task.closed_by_id = closed_by_id
    db.session.commit()
    track_activity(f'closed war room task "{task.title}"', war_room_id=war_room_id)
    task = call_modules_hook('on_postload_war_room_task_close', task)
    return task


def war_room_task_reopen(war_room_id, task_id):
    task = war_room_task_get(war_room_id, task_id)
    task.closed_at = None
    task.closed_by_id = None
    db.session.commit()
    track_activity(f'reopened war room task "{task.title}"', war_room_id=war_room_id)
    task = call_modules_hook('on_postload_war_room_task_reopen', task)
    return task


def war_room_task_delete(war_room_id, task_id):
    task = war_room_task_get(war_room_id, task_id)
    title = task.title
    db.session.delete(task)
    db.session.commit()
    track_activity(f'deleted war room task "{title}"', war_room_id=war_room_id)
    call_modules_hook('on_postload_war_room_task_delete',
                      {'war_room_id': war_room_id, 'task_id': task_id})


def war_room_task_used_tags(war_room_id):
    """Return the distinct set of tags already used on this room's tasks.

    Powers autocomplete on the tag input. Case is preserved on first
    occurrence.
    """
    rows = (
        db.session.query(WarRoomTask.tags)
        .filter(
            WarRoomTask.war_room_id == war_room_id,
            WarRoomTask.tags.isnot(None),
            WarRoomTask.tags != '',
        )
        .all()
    )
    seen = {}
    for (raw,) in rows:
        for t in (raw or '').split(','):
            t = t.strip()
            if not t:
                continue
            key = t.lower()
            if key not in seen:
                seen[key] = t
    return sorted(seen.values(), key=lambda s: s.lower())
