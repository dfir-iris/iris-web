#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""War-room timelines REST routes."""

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
from app.business.war_room_timelines import (
    create_timeline,
    create_timeline_event,
    delete_timeline,
    delete_timeline_event,
    get_timeline,
    list_timeline_events,
    list_timelines,
    update_timeline,
    update_timeline_event,
)
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


war_rooms_timelines_blueprint = Blueprint(
    'war_rooms_timelines_rest_v2', __name__,
    url_prefix='/<int:war_room_id>/timelines'
)


def _serialize_timeline(t):
    return {
        'timeline_id': t.timeline_id,
        'war_room_id': t.war_room_id,
        'name': t.name,
        'description': t.description,
        'color': t.color,
        'is_default': bool(t.is_default),
        'created_at': t.created_at.isoformat() if t.created_at else None,
        'created_by_id': t.created_by_id,
    }


def _serialize_event(e):
    return {
        'id': e.id,
        'timeline_id': e.timeline_id,
        'case_id': e.case_id,
        'event_id': e.event_id,
        'title': e.title,
        'content': e.content,
        'event_date': e.event_date.isoformat() if e.event_date else None,
        'event_tz': e.event_tz,
        'color': e.color,
        # `category` may be absent on databases predating the column —
        # tolerate that so the route still returns valid JSON when the
        # migration hasn't been run yet.
        'category': getattr(e, 'category', None),
        'created_at': e.created_at.isoformat() if e.created_at else None,
        'created_by_id': e.created_by_id,
    }


@war_rooms_timelines_blueprint.get('')
@ac_api_requires()
def list_room_timelines(war_room_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    return response_api_success(
        data=[_serialize_timeline(t) for t in list_timelines(war_room_id)]
    )


@war_rooms_timelines_blueprint.post('')
@ac_api_requires()
def create_room_timeline(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        t = create_timeline(
            war_room_id, name=raw.get('name'),
            description=raw.get('description'), color=raw.get('color'),
            created_by_id=iris_current_user.id,
        )
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_created(_serialize_timeline(t))


@war_rooms_timelines_blueprint.patch('/<int:timeline_id>')
@ac_api_requires()
def update_room_timeline(war_room_id, timeline_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        t = update_timeline(war_room_id, timeline_id,
                            name=raw.get('name'),
                            description=raw.get('description'),
                            color=raw.get('color'))
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_success(_serialize_timeline(t))


@war_rooms_timelines_blueprint.delete('/<int:timeline_id>')
@ac_api_requires()
def delete_room_timeline(war_room_id, timeline_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        delete_timeline(war_room_id, timeline_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_deleted()


@war_rooms_timelines_blueprint.get('/events')
@ac_api_requires()
def list_events(war_room_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    timeline_ids_raw = request.args.get('timeline_ids', type=str)
    timeline_ids = None
    if timeline_ids_raw:
        try:
            timeline_ids = [int(x) for x in timeline_ids_raw.split(',') if x.strip()]
        except ValueError:
            return response_api_error('Invalid timeline_ids')
    rows = list_timeline_events(war_room_id, timeline_ids=timeline_ids)
    return response_api_success(data=[_serialize_event(e) for e in rows])


def _parse_event_date(raw):
    if raw is None or raw == '':
        return None
    if isinstance(raw, datetime):
        return raw
    if not isinstance(raw, str):
        raise BusinessProcessingError('event_date must be an ISO date string')
    try:
        return datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        raise BusinessProcessingError('event_date must be an ISO date string')


@war_rooms_timelines_blueprint.post('/<int:timeline_id>/events')
@ac_api_requires()
def add_event(war_room_id, timeline_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        event_date = _parse_event_date(raw.get('event_date'))
        row = create_timeline_event(
            war_room_id, timeline_id,
            title=raw.get('title'),
            content=raw.get('content'),
            event_date=event_date,
            event_tz=raw.get('event_tz'),
            color=raw.get('color'),
            category=raw.get('category'),
            case_id=raw.get('case_id'),
            event_id=raw.get('event_id'),
            created_by_id=iris_current_user.id,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_created(_serialize_event(row))


@war_rooms_timelines_blueprint.patch('/events/<int:event_id>')
@ac_api_requires()
def patch_event(war_room_id, event_id):
    """Partial update for a war-room timeline event.

    Body fields are all optional; only those present are touched. A
    missing key is left as-is; an explicit `null` clears the field.
    `timeline_id` re-parents the event (drag-between-timelines).
    """
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    kwargs = {}
    for key in ('title', 'content', 'event_tz', 'color', 'category',
                'timeline_id'):
        if key in raw:
            kwargs[key] = raw[key]
    if 'event_date' in raw:
        try:
            kwargs['event_date'] = _parse_event_date(raw['event_date'])
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())
    try:
        row = update_timeline_event(war_room_id, event_id, **kwargs)
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_success(_serialize_event(row))


@war_rooms_timelines_blueprint.delete('/events/<int:event_id>')
@ac_api_requires()
def remove_event(war_room_id, event_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        delete_timeline_event(war_room_id, event_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_deleted()
