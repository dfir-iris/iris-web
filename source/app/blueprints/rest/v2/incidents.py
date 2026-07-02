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
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from flask import Blueprint
from flask import request
from flask import session
from marshmallow.exceptions import ValidationError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_current_user_has_customer_access
from app.blueprints.access_controls import ac_current_user_has_permission
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.v2.incidents_routes.investigation_progress import (
    incidents_investigation_progress_blueprint,
)
from app.business.incidents import incident_add_alerts
from app.business.incidents import incident_escalate_to_case
from app.business.incidents import incident_remove_alert
from app.business.incidents import incidents_create
from app.business.incidents import incidents_delete
from app.business.incidents import incidents_get
from app.business.incidents import incidents_search
from app.business.incidents import incidents_update
from app.models.authorization import Permissions
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.schema.marshables import IncidentSchema


# Immutable-on-update fields (CVE class fixed by _ALERT_READONLY_UPDATE_FIELDS
# on the alerts blueprint — re-attributing incident_customer_id would let a
# user with write access to one tenant move an incident into another).
_INCIDENT_READONLY_UPDATE_FIELDS = frozenset({
    'incident_id',
    'incident_customer_id',
    'incident_creation_time',
    'incident_case_id',
    'incident_dedupe_key',
    'incident_source_rule_id',
})


def _strip_readonly(payload):
    if not isinstance(payload, dict):
        return payload
    return {k: v for k, v in payload.items() if k not in _INCIDENT_READONLY_UPDATE_FIELDS}


incidents_blueprint = Blueprint('incidents_rest_v2', __name__, url_prefix='/incidents')
incidents_blueprint.register_blueprint(incidents_investigation_progress_blueprint)

_schema = IncidentSchema()


@incidents_blueprint.get('')
@ac_api_requires(Permissions.incidents_read)
def list_incidents():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    user_filter = iris_current_user.id
    if ac_current_user_has_permission(Permissions.server_administrator):
        user_filter = None

    paginated = incidents_search(
        customer_id=request.args.get('customer_id', type=int),
        status_id=request.args.get('status_id', type=int),
        title=request.args.get('title'),
        user_identifier_filter=user_filter,
        page=page,
        per_page=per_page,
        sort=request.args.get('sort'),
    )
    return response_api_paginated(_schema, paginated)


@incidents_blueprint.post('')
@ac_api_requires(Permissions.incidents_write)
def create_incident():
    payload = request.get_json() or {}
    try:
        incident = _schema.load(payload)
    except ValidationError as exc:
        return response_api_error('Data error', data=exc.messages)
    if not ac_current_user_has_customer_access(incident.incident_customer_id):
        return response_api_error('User not entitled to create incidents for the client')

    alert_ids = payload.get('alert_ids') or []
    result = incidents_create(incident)
    if alert_ids:
        incident_add_alerts(result, alert_ids)
    return response_api_created(_schema.dump(result))


@incidents_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.incidents_read)
def read_incident(identifier):
    try:
        incident = incidents_get(
            iris_current_user,
            session.get('permissions') or 0,
            identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_schema.dump(incident))


@incidents_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.incidents_write)
def update_incident(identifier):
    try:
        incident = incidents_get(
            iris_current_user,
            session.get('permissions') or 0,
            identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    payload = _strip_readonly(request.get_json() or {})
    try:
        # partial load lets the schema validate types without requiring all fields
        _schema.load(payload, instance=incident, partial=True)
    except ValidationError as exc:
        return response_api_error('Data error', data=exc.messages)
    result = incidents_update(incident, payload)
    return response_api_success(_schema.dump(result))


@incidents_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.incidents_delete)
def delete_incident(identifier):
    try:
        incident = incidents_get(
            iris_current_user,
            session.get('permissions') or 0,
            identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    incidents_delete(incident)
    return response_api_deleted()


@incidents_blueprint.post('/<int:identifier>/alerts')
@ac_api_requires(Permissions.incidents_write)
def add_alerts(identifier):
    try:
        incident = incidents_get(
            iris_current_user,
            session.get('permissions') or 0,
            identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    payload = request.get_json() or {}
    alert_ids = payload.get('alert_ids') or []
    if not isinstance(alert_ids, list):
        return response_api_error('alert_ids must be a list of integers')
    result = incident_add_alerts(incident, alert_ids)
    return response_api_success(_schema.dump(result))


@incidents_blueprint.delete('/<int:identifier>/alerts/<int:alert_id>')
@ac_api_requires(Permissions.incidents_write)
def remove_alert(identifier, alert_id):
    try:
        incident = incidents_get(
            iris_current_user,
            session.get('permissions') or 0,
            identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    result = incident_remove_alert(incident, alert_id)
    return response_api_success(_schema.dump(result))


@incidents_blueprint.post('/<int:identifier>/escalate')
@ac_api_requires(Permissions.incidents_write)
def escalate(identifier):
    try:
        incident = incidents_get(
            iris_current_user,
            session.get('permissions') or 0,
            identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    payload = request.get_json() or {}
    try:
        case = incident_escalate_to_case(
            incident,
            template_id=payload.get('template_id'),
            case_title=payload.get('case_title'),
            note=payload.get('note'),
            import_as_event=bool(payload.get('import_as_event', False)),
            case_tags=payload.get('case_tags', '') or '',
        )
    except BusinessProcessingError as exc:
        return response_api_error(exc.get_message(), data=exc.get_data())
    return response_api_success({
        'incident_id': incident.incident_id,
        'case_id': case.case_id,
    })
