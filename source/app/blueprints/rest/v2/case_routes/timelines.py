#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.

"""
v2 REST routes for the per-case "named timelines" feature.

URL layout (mounted under `/api/v2/cases/<int:case_identifier>/timelines`):

    GET    /                  list every timeline on the case
    POST   /                  create a new timeline
    GET    /<int:id>          fetch a single timeline
    PUT    /<int:id>          update name / description / color
    DELETE /<int:id>          delete (not allowed on the default timeline)

Response shape follows the rest of the v2 API:
`response_api_success(data=...)` ships the data dict directly at the
top level (no envelope). Error responses are HTTP 400 with a
`{message: "..."}` body via `response_api_error`.
"""

from flask import Blueprint
from flask import request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.business.cases import cases_exists
from app.business.case_timelines import case_timeline_create
from app.business.case_timelines import case_timeline_delete
from app.business.case_timelines import case_timeline_get
from app.business.case_timelines import case_timeline_list
from app.business.case_timelines import case_timeline_update
from app.models.authorization import CaseAccessLevel
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


case_timelines_blueprint = Blueprint(
    'case_timelines_rest_v2', __name__,
    url_prefix='/<int:case_identifier>/timelines'
)


def _serialize(timeline):
    return {
        'timeline_id': timeline.timeline_id,
        'case_id': timeline.case_id,
        'name': timeline.name,
        'description': timeline.description,
        'color': timeline.color,
        'is_default': bool(timeline.is_default),
        'created_at': timeline.created_at.isoformat() if timeline.created_at else None,
        'created_by_id': timeline.created_by_id,
    }


def _require_read_access(case_identifier):
    if not cases_exists(case_identifier):
        return response_api_not_found()
    if not ac_fast_check_current_user_has_case_access(
        case_identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]
    ):
        return ac_api_return_access_denied(caseid=case_identifier)
    return None


def _require_full_access(case_identifier):
    if not cases_exists(case_identifier):
        return response_api_not_found()
    if not ac_fast_check_current_user_has_case_access(
        case_identifier, [CaseAccessLevel.full_access]
    ):
        return ac_api_return_access_denied(caseid=case_identifier)
    return None


@case_timelines_blueprint.get('')
@ac_api_requires()
def list_timelines(case_identifier):
    err = _require_read_access(case_identifier)
    if err is not None:
        return err
    return response_api_success(
        data=[_serialize(t) for t in case_timeline_list(case_identifier)]
    )


@case_timelines_blueprint.post('')
@ac_api_requires()
def create_timeline(case_identifier):
    err = _require_full_access(case_identifier)
    if err is not None:
        return err

    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')

    try:
        timeline = case_timeline_create(
            case_identifier,
            name=raw.get('name'),
            description=raw.get('description'),
            color=raw.get('color'),
            created_by_id=iris_current_user.id,
        )
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())

    return response_api_created(_serialize(timeline))


@case_timelines_blueprint.get('/<int:timeline_id>')
@ac_api_requires()
def get_timeline(case_identifier, timeline_id):
    err = _require_read_access(case_identifier)
    if err is not None:
        return err
    try:
        timeline = case_timeline_get(case_identifier, timeline_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(data=_serialize(timeline))


@case_timelines_blueprint.put('/<int:timeline_id>')
@ac_api_requires()
def update_timeline(case_identifier, timeline_id):
    err = _require_full_access(case_identifier)
    if err is not None:
        return err

    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')

    try:
        timeline = case_timeline_update(
            case_identifier, timeline_id,
            name=raw.get('name'),
            description=raw.get('description'),
            color=raw.get('color'),
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())

    return response_api_success(data=_serialize(timeline))


@case_timelines_blueprint.delete('/<int:timeline_id>')
@ac_api_requires()
def delete_timeline(case_identifier, timeline_id):
    err = _require_full_access(case_identifier)
    if err is not None:
        return err
    try:
        case_timeline_delete(case_identifier, timeline_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_deleted()
