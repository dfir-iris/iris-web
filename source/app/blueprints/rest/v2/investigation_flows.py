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
from app.blueprints.access_controls import ac_current_user_has_customer_access
from app.blueprints.access_controls import ac_current_user_permissions_mask
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
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.schema.marshables import InvestigationFlowSchema
from app.schema.marshables import InvestigationFlowStepSchema


# Fields the caller must never set / mutate via the request body — see
# `_RULE_READONLY_FIELDS` on the rules blueprint for the same rationale.
_FLOW_READONLY_FIELDS = frozenset({
    'flow_id',
    'flow_uuid',
    'flow_created_by',
    'flow_created_at',
    'flow_updated_at',
})


def _strip_readonly(payload):
    if not isinstance(payload, dict):
        return payload
    return {k: v for k, v in payload.items() if k not in _FLOW_READONLY_FIELDS}


def _caller():
    """See `_caller` on the rules blueprint — same rationale: use the
    canonical permission-mask helper so session and API-key auth paths
    both resolve to the caller's real permissions."""
    return iris_current_user, ac_current_user_permissions_mask()


investigation_flows_blueprint = Blueprint(
    'investigation_flows_rest_v2', __name__, url_prefix='/investigation-flows'
)

_flow_schema = InvestigationFlowSchema()
_step_schema = InvestigationFlowStepSchema()


@investigation_flows_blueprint.get('')
@ac_api_requires(Permissions.investigation_flows_read)
def list_flows():
    user, perms = _caller()
    return response_api_success([_flow_schema.dump(f) for f in flows_list(user, perms)])


@investigation_flows_blueprint.post('')
@ac_api_requires(Permissions.investigation_flows_write)
def create_flow():
    user, perms = _caller()
    payload = _strip_readonly(request.get_json() or {})
    # Server-owned attribution — set AFTER stripping any spoofed value.
    payload['flow_created_by'] = iris_current_user.id
    try:
        flow = _flow_schema.load(payload)
    except ValidationError as exc:
        return response_api_error('Data error', data=exc.messages)
    try:
        result = flows_create(
            user, perms, flow,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except BusinessProcessingError as exc:
        return response_api_error(exc.get_message(), data=exc.get_data())
    return response_api_created(_flow_schema.dump(result))


@investigation_flows_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.investigation_flows_read)
def read_flow(identifier):
    user, perms = _caller()
    try:
        flow = flows_get(
            user, perms, identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_flow_schema.dump(flow))


@investigation_flows_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.investigation_flows_write)
def update_flow(identifier):
    user, perms = _caller()
    try:
        flow = flows_get(
            user, perms, identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    payload = _strip_readonly(request.get_json() or {})
    try:
        _flow_schema.load(payload, instance=flow, partial=True)
    except ValidationError as exc:
        return response_api_error('Data error', data=exc.messages)
    try:
        result = flows_update(
            user, perms, flow, payload,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except BusinessProcessingError as exc:
        return response_api_error(exc.get_message(), data=exc.get_data())
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_flow_schema.dump(result))


@investigation_flows_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.investigation_flows_write)
def delete_flow(identifier):
    user, perms = _caller()
    try:
        flow = flows_get(
            user, perms, identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    flows_delete(flow)
    return response_api_deleted()


@investigation_flows_blueprint.post('/<int:identifier>/steps')
@ac_api_requires(Permissions.investigation_flows_write)
def create_step(identifier):
    user, perms = _caller()
    try:
        flow = flows_get(
            user, perms, identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
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
    user, perms = _caller()
    try:
        step = flow_step_get(
            user, perms, step_id,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    # Enforce path/body consistency — a step id from a foreign flow must
    # 404 the same way as a non-existent step, so the URL can't be used
    # to smuggle a step-under-flow reassignment.
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
    user, perms = _caller()
    try:
        step = flow_step_get(
            user, perms, step_id,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    if step.flow_id != flow_id:
        return response_api_not_found()
    flow_step_delete(step)
    return response_api_deleted()


@investigation_flows_blueprint.post('/<int:identifier>/deploy')
@ac_api_requires(Permissions.investigation_flows_write)
def deploy(identifier):
    """Back-fill this flow onto historical alerts / alert clusters whose
    investigation-flow FK is empty and whose contents match the flow's
    own conditions. Returns per-target attach counts.

    Loaded through the scope-gated `flows_get` — a caller who can't act
    on every tenant in `flow.flow_customer_scope` gets a 404 the same
    way the read endpoint would, closing the deploy-then-cross-tenant
    path the security review flagged."""
    user, perms = _caller()
    try:
        flow = flows_get(
            user, perms, identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    alerts_attached, clusters_attached = deploy_flow(flow)
    return response_api_success({
        'flow_id': flow.flow_id,
        'alerts_attached': alerts_attached,
        'clusters_attached': clusters_attached,
    })
