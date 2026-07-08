#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""REST routes for the linked-case-timelines projection.

Read-only surface — see `app.business.war_room_linked_case_timelines`
for the rationale. Writes to case timelines still go through the
case-side timelines endpoints; this module only projects case events
into the war-room view so the frontend can render them alongside
native `WarRoomTimelineEvent` rows.
"""

from flask import Blueprint, request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.v2.war_rooms.access import require_war_room_read
from app.business.war_room_linked_case_timelines import (
    list_linked_case_events,
    list_linked_case_timelines,
)


war_rooms_linked_case_timelines_blueprint = Blueprint(
    'war_rooms_linked_case_timelines_rest_v2', __name__,
    url_prefix='/<int:war_room_id>/linked-case-timelines',
)


@war_rooms_linked_case_timelines_blueprint.get('')
@ac_api_requires()
def list_available(war_room_id):
    """Nested `case -> timelines` tree the sidebar renders as toggle
    sources. Cases the caller can't read are silently dropped by the
    business layer so we don't leak their existence."""
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    tree = list_linked_case_timelines(war_room_id, iris_current_user.id)
    return response_api_success(data=tree)


@war_rooms_linked_case_timelines_blueprint.get('/events')
@ac_api_requires()
def list_events(war_room_id):
    """Return case events for the requested timelines, shaped like
    native war-room events. `case_timeline_ids` is CSV in the query
    string — matches the shape of `/timelines/events?timeline_ids=` so
    the frontend can build the URL the same way."""
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err

    raw = request.args.get('case_timeline_ids', type=str)
    if not raw:
        # No timelines requested → no events. Matches the "empty
        # selection = no case events" default state the sidebar
        # ships with.
        return response_api_success(data=[])
    try:
        ids = [int(x) for x in raw.split(',') if x.strip()]
    except ValueError:
        return response_api_error('Invalid case_timeline_ids')

    events = list_linked_case_events(war_room_id, iris_current_user.id, ids)
    return response_api_success(data=events)
