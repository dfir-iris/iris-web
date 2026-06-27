#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""War-room tasks REST routes."""

from datetime import datetime

from flask import Blueprint, request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.v2.war_rooms.access import require_war_room_read
from app.blueprints.rest.v2.war_rooms.access import require_war_room_write
from app.business.war_room_chat import emit_system_event
from app.business.war_room_tasks import (
    war_room_task_close,
    war_room_task_create,
    war_room_task_delete,
    war_room_task_get,
    war_room_task_list,
    war_room_task_reopen,
    war_room_task_update,
)
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


war_rooms_tasks_blueprint = Blueprint(
    'war_rooms_tasks_rest_v2', __name__, url_prefix='/<int:war_room_id>/tasks'
)


def _parse_due(raw):
    if raw is None or raw == '':
        return None
    if isinstance(raw, datetime):
        return raw
    if not isinstance(raw, str):
        raise BusinessProcessingError('due_at must be an ISO date string')
    try:
        # Accept both "YYYY-MM-DD" and full ISO.
        if len(raw) == 10:
            return datetime.fromisoformat(raw)
        return datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        raise BusinessProcessingError('due_at must be an ISO date string')


def _serialize_row(row):
    return {
        'task_id': row.task_id,
        'war_room_id': row.war_room_id,
        'title': row.title,
        'description': row.description,
        'status_id': row.status_id,
        'assignee_id': row.assignee_id,
        'assignee_login': row.assignee_login,
        'assignee_name': row.assignee_name,
        'due_at': row.due_at.isoformat() if row.due_at else None,
        'source_case_id': row.source_case_id,
        'source_case_task_id': row.source_case_task_id,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'created_by_id': row.created_by_id,
        'closed_at': row.closed_at.isoformat() if row.closed_at else None,
        'closed_by_id': row.closed_by_id,
        'tags': row.tags,
    }


def _serialize_obj(task):
    return {
        'task_id': task.task_id,
        'war_room_id': task.war_room_id,
        'title': task.title,
        'description': task.description,
        'status_id': task.status_id,
        'assignee_id': task.assignee_id,
        'due_at': task.due_at.isoformat() if task.due_at else None,
        'source_case_id': task.source_case_id,
        'source_case_task_id': task.source_case_task_id,
        'created_at': task.created_at.isoformat() if task.created_at else None,
        'created_by_id': task.created_by_id,
        'closed_at': task.closed_at.isoformat() if task.closed_at else None,
        'closed_by_id': task.closed_by_id,
        'tags': task.tags,
    }


@war_rooms_tasks_blueprint.get('')
@ac_api_requires()
def list_tasks(war_room_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    rows = war_room_task_list(war_room_id)
    return response_api_success(data=[_serialize_row(r) for r in rows])


@war_rooms_tasks_blueprint.post('')
@ac_api_requires()
def create_task(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        due_at = _parse_due(raw.get('due_at'))
        task = war_room_task_create(
            war_room_id,
            title=raw.get('title'),
            description=raw.get('description'),
            status_id=raw.get('status_id'),
            assignee_id=raw.get('assignee_id'),
            due_at=due_at,
            source_case_id=raw.get('source_case_id'),
            source_case_task_id=raw.get('source_case_task_id'),
            tags=raw.get('tags'),
            created_by_id=iris_current_user.id,
        )
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    emit_system_event(
        war_room_id, 'task_assigned',
        f'Created task: {task.title}',
        author_id=iris_current_user.id,
        ref_type='war_room_task', ref_id=task.task_id,
    )
    return response_api_created(_serialize_obj(task))


@war_rooms_tasks_blueprint.patch('/<int:task_id>')
@ac_api_requires()
def update_task(war_room_id, task_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        fields = {k: raw[k] for k in raw if k in
                  ('title', 'description', 'status_id', 'assignee_id',
                   'source_case_id', 'source_case_task_id', 'tags')}
        if 'due_at' in raw:
            fields['due_at'] = _parse_due(raw['due_at'])
        task = war_room_task_update(war_room_id, task_id, **fields)
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_success(_serialize_obj(task))


@war_rooms_tasks_blueprint.post('/<int:task_id>/close')
@ac_api_requires()
def close_task(war_room_id, task_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        task = war_room_task_close(war_room_id, task_id,
                                    closed_by_id=iris_current_user.id)
    except ObjectNotFoundError:
        return response_api_not_found()
    emit_system_event(
        war_room_id, 'task_completed',
        f'Closed task: {task.title}',
        author_id=iris_current_user.id,
        ref_type='war_room_task', ref_id=task.task_id,
    )
    return response_api_success(_serialize_obj(task))


@war_rooms_tasks_blueprint.post('/<int:task_id>/reopen')
@ac_api_requires()
def reopen_task(war_room_id, task_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        task = war_room_task_reopen(war_room_id, task_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    emit_system_event(
        war_room_id, 'task_assigned',
        f'Reopened task: {task.title}',
        author_id=iris_current_user.id,
        ref_type='war_room_task', ref_id=task.task_id,
    )
    return response_api_success(_serialize_obj(task))


@war_rooms_tasks_blueprint.delete('/<int:task_id>')
@ac_api_requires()
def delete_task(war_room_id, task_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        war_room_task_delete(war_room_id, task_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_deleted()
