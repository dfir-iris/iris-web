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

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_current_user_has_customer_access
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.business.alerts import alerts_get
from app.business.investigation_flows import alert_progress_list
from app.business.investigation_flows import alert_progress_record
from app.business.investigation_flows import alert_progress_uncheck
from app.models.authorization import Permissions
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.schema.marshables import AlertInvestigationProgressSchema


alerts_investigation_progress_blueprint = Blueprint(
    'alerts_investigation_progress_rest_v2', __name__
)

_schema = AlertInvestigationProgressSchema()


def _load_alert(identifier):
    return alerts_get(
        iris_current_user,
        session.get('permissions') or 0,
        identifier,
        fallback_customer_access=ac_current_user_has_customer_access,
    )


@alerts_investigation_progress_blueprint.get('/<int:identifier>/investigation-progress')
@ac_api_requires(Permissions.alerts_read)
def list_progress(identifier):
    try:
        alert = _load_alert(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    rows = alert_progress_list(alert)
    flow = alert.investigation_flow
    return response_api_success({
        'flow_id': flow.flow_id if flow else None,
        'flow_name': flow.flow_name if flow else None,
        'steps': [
            {
                'step_id': s.step_id,
                'step_order': s.step_order,
                'step_title': s.step_title,
                'step_description': s.step_description,
                'step_is_required': s.step_is_required,
            }
            for s in (flow.steps if flow else [])
        ],
        'progress': [_schema.dump(r) for r in rows],
    })


@alerts_investigation_progress_blueprint.post('/<int:identifier>/investigation-progress/<int:step_id>')
@ac_api_requires(Permissions.alerts_write)
def record_progress(identifier, step_id):
    try:
        alert = _load_alert(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    payload = request.get_json() or {}
    try:
        row = alert_progress_record(
            alert, step_id, iris_current_user.id, note=payload.get('note')
        )
    except BusinessProcessingError as exc:
        return response_api_error(exc.get_message(), data=exc.get_data())
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_schema.dump(row))


@alerts_investigation_progress_blueprint.delete('/<int:identifier>/investigation-progress/<int:step_id>')
@ac_api_requires(Permissions.alerts_write)
def uncheck_progress(identifier, step_id):
    try:
        alert = _load_alert(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    alert_progress_uncheck(alert, step_id)
    return response_api_deleted()
