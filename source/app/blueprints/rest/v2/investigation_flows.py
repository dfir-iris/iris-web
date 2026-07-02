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
from marshmallow.exceptions import ValidationError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.business.investigation_flows import deploy_flow
from app.business.investigation_flows import flow_step_create
from app.business.investigation_flows import flow_step_delete
from app.business.investigation_flows import flow_step_get
from app.business.investigation_flows import flow_step_update
from app.business.investigation_flows import flows_create
from app.business.investigation_flows import flows_delete
from app.business.investigation_flows import flows_get
from app.business.investigation_flows import flows_list
from app.business.investigation_flows import flows_update
from app.models.authorization import Permissions
from app.models.errors import ObjectNotFoundError
from app.schema.marshables import InvestigationFlowSchema
from app.schema.marshables import InvestigationFlowStepSchema


investigation_flows_blueprint = Blueprint(
    'investigation_flows_rest_v2', __name__, url_prefix='/investigation-flows'
)

_flow_schema = InvestigationFlowSchema()
_step_schema = InvestigationFlowStepSchema()


@investigation_flows_blueprint.get('')
@ac_api_requires(Permissions.investigation_flows_read)
def list_flows():
    customer_id = request.args.get('customer_id', type=int)
    return response_api_success([_flow_schema.dump(f) for f in flows_list(customer_id=customer_id)])


@investigation_flows_blueprint.post('')
@ac_api_requires(Permissions.investigation_flows_write)
def create_flow():
    payload = request.get_json() or {}
    payload.setdefault('flow_created_by', iris_current_user.id)
    try:
        flow = _flow_schema.load(payload)
    except ValidationError as exc:
        return response_api_error('Data error', data=exc.messages)
    return response_api_created(_flow_schema.dump(flows_create(flow)))


@investigation_flows_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.investigation_flows_read)
def read_flow(identifier):
    try:
        flow = flows_get(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_flow_schema.dump(flow))


@investigation_flows_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.investigation_flows_write)
def update_flow(identifier):
    try:
        flow = flows_get(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    payload = request.get_json() or {}
    try:
        _flow_schema.load(payload, instance=flow, partial=True)
    except ValidationError as exc:
        return response_api_error('Data error', data=exc.messages)
    return response_api_success(_flow_schema.dump(flows_update(flow, payload)))


@investigation_flows_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.investigation_flows_write)
def delete_flow(identifier):
    try:
        flow = flows_get(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    flows_delete(flow)
    return response_api_deleted()


@investigation_flows_blueprint.post('/<int:identifier>/steps')
@ac_api_requires(Permissions.investigation_flows_write)
def create_step(identifier):
    try:
        flow = flows_get(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    payload = request.get_json() or {}
    try:
        step = _step_schema.load(payload)
    except ValidationError as exc:
        return response_api_error('Data error', data=exc.messages)
    return response_api_created(_step_schema.dump(flow_step_create(flow, step)))


@investigation_flows_blueprint.put('/<int:flow_id>/steps/<int:step_id>')
@ac_api_requires(Permissions.investigation_flows_write)
def update_step(flow_id, step_id):
    try:
        step = flow_step_get(step_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    if step.flow_id != flow_id:
        return response_api_not_found()
    payload = request.get_json() or {}
    try:
        _step_schema.load(payload, instance=step, partial=True)
    except ValidationError as exc:
        return response_api_error('Data error', data=exc.messages)
    return response_api_success(_step_schema.dump(flow_step_update(step, payload)))


@investigation_flows_blueprint.delete('/<int:flow_id>/steps/<int:step_id>')
@ac_api_requires(Permissions.investigation_flows_write)
def delete_step(flow_id, step_id):
    try:
        step = flow_step_get(step_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    if step.flow_id != flow_id:
        return response_api_not_found()
    flow_step_delete(step)
    return response_api_deleted()


@investigation_flows_blueprint.post('/<int:identifier>/deploy')
@ac_api_requires(Permissions.investigation_flows_write)
def deploy(identifier):
    """Back-fill this flow onto historical alerts / incidents whose
    investigation-flow FK is empty and whose contents match the flow's
    own conditions. Returns per-target attach counts."""
    try:
        flow = flows_get(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    alerts_attached, incidents_attached = deploy_flow(flow)
    return response_api_success({
        'flow_id': flow.flow_id,
        'alerts_attached': alerts_attached,
        'incidents_attached': incidents_attached,
    })
