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
    duplicate_event,
    event_asset_ids,
    event_children_count,
    event_ioc_ids,
    get_timeline,
    list_timeline_events,
    list_timelines,
    set_event_assets,
    set_event_iocs,
    toggle_event_flag,
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
    """Wire shape for a native war-room event.

    Matches the case-timeline event card's expectations — the card
    reads `uuid`, `source`, `raw`, `tags`, `is_flagged`, plus the
    hydrated `assets` / `iocs` id lists and the `children_count` badge.
    `war_room_source` is intentionally omitted here (native events);
    the projection layer sets it to `'case'` on case-sourced rows so
    the frontend can discriminate. Per-event comments aren't part of
    the war-room event surface — war-room chat plays that role.
    """
    return {
        'id': e.id,
        # `uuid` may be absent on databases predating the column —
        # `getattr` fallback lets the route survive a boot where the
        # migration hasn't been run yet. Same for the other new fields.
        'uuid': str(getattr(e, 'uuid', '') or ''),
        'timeline_id': e.timeline_id,
        'parent_id': getattr(e, 'parent_id', None),
        'case_id': e.case_id,
        'event_id': e.event_id,
        'title': e.title,
        'content': e.content,
        'raw': getattr(e, 'raw', None),
        'source': getattr(e, 'source', None),
        'tags': getattr(e, 'tags', None),
        'is_flagged': bool(getattr(e, 'is_flagged', False)),
        'event_date': e.event_date.isoformat() if e.event_date else None,
        'event_tz': e.event_tz,
        'color': e.color,
        'category': getattr(e, 'category', None),
        'modification_history': getattr(e, 'modification_history', None),
        # Hydrated read-side extras. Kept as arrays / ints so the
        # frontend's derived-state code can spot changes cheaply.
        'assets': event_asset_ids(e.id),
        'iocs': event_ioc_ids(e.id),
        'children_count': event_children_count(e.id),
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
            source=raw.get('source'),
            raw=raw.get('raw'),
            tags=raw.get('tags'),
            is_flagged=bool(raw.get('is_flagged', False)),
            parent_id=raw.get('parent_id'),
            asset_ids=raw.get('asset_ids'),
            ioc_ids=raw.get('ioc_ids'),
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
    # Only fields the client actually included are forwarded — the
    # business layer's sentinel-based partial-update contract needs
    # "omitted" to be distinguishable from "cleared". `is_flagged`
    # accepts either a bool or something coerceable to one.
    for key in ('title', 'content', 'event_tz', 'color', 'category',
                'timeline_id', 'source', 'raw', 'tags', 'is_flagged',
                'parent_id', 'asset_ids', 'ioc_ids'):
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


@war_rooms_timelines_blueprint.post('/events/<int:event_id>/flag')
@ac_api_requires()
def flag_event(war_room_id, event_id):
    """Toggle the triage flag on an event. No body — one click, server
    flips the boolean and returns the fresh row."""
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        row = toggle_event_flag(war_room_id, event_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_serialize_event(row))


@war_rooms_timelines_blueprint.post('/events/<int:event_id>/duplicate')
@ac_api_requires()
def duplicate_event_route(war_room_id, event_id):
    """Shallow-copy an event onto the same timeline. Convenience for the
    three-dot menu; the frontend could POST the fields itself but this
    keeps the "copy" affordance a one-click operation."""
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        row = duplicate_event(war_room_id, event_id,
                              created_by_id=iris_current_user.id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_created(_serialize_event(row))


@war_rooms_timelines_blueprint.put('/events/<int:event_id>/assets')
@ac_api_requires()
def replace_event_assets(war_room_id, event_id):
    """Replace the event's asset associations with the given id list.
    Passing `[]` detaches everything; missing / non-list body → 400."""
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    ids = raw.get('asset_ids') if isinstance(raw, dict) else None
    if not isinstance(ids, list):
        return response_api_error('asset_ids must be a list of integers')
    try:
        set_event_assets(war_room_id, event_id, ids)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success({'asset_ids': event_asset_ids(event_id)})


@war_rooms_timelines_blueprint.put('/events/<int:event_id>/iocs')
@ac_api_requires()
def replace_event_iocs(war_room_id, event_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    ids = raw.get('ioc_ids') if isinstance(raw, dict) else None
    if not isinstance(ids, list):
        return response_api_error('ioc_ids must be a list of integers')
    try:
        set_event_iocs(war_room_id, event_id, ids)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success({'ioc_ids': event_ioc_ids(event_id)})
