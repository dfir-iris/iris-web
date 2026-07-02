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
from app.business.incident_rules import backfill_rule
from app.business.incident_rules import rule_dry_run
from app.business.incident_rules import rules_create
from app.business.incident_rules import rules_delete
from app.business.incident_rules import rules_get
from app.business.incident_rules import rules_list
from app.business.incident_rules import rules_update
from app.models.authorization import Permissions
from app.models.errors import ObjectNotFoundError
from app.schema.marshables import IncidentRuleSchema


incident_rules_blueprint = Blueprint('incident_rules_rest_v2', __name__, url_prefix='/incident-rules')

_schema = IncidentRuleSchema()


@incident_rules_blueprint.get('')
@ac_api_requires(Permissions.incident_rules_read)
def list_rules():
    rows = rules_list(customer_id=None)
    return response_api_success([_schema.dump(r) for r in rows])


@incident_rules_blueprint.post('')
@ac_api_requires(Permissions.incident_rules_write)
def create_rule():
    payload = request.get_json() or {}
    payload.setdefault('rule_created_by', iris_current_user.id)
    try:
        rule = _schema.load(payload)
    except ValidationError as exc:
        return response_api_error('Data error', data=exc.messages)
    result = rules_create(rule)
    return response_api_created(_schema.dump(result))


@incident_rules_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.incident_rules_read)
def read_rule(identifier):
    try:
        rule = rules_get(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_schema.dump(rule))


@incident_rules_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.incident_rules_write)
def update_rule(identifier):
    try:
        rule = rules_get(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    payload = request.get_json() or {}
    try:
        _schema.load(payload, instance=rule, partial=True)
    except ValidationError as exc:
        return response_api_error('Data error', data=exc.messages)
    result = rules_update(rule, payload)
    return response_api_success(_schema.dump(result))


@incident_rules_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.incident_rules_write)
def delete_rule(identifier):
    try:
        rule = rules_get(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    rules_delete(rule)
    return response_api_deleted()


@incident_rules_blueprint.post('/<int:identifier>/test')
@ac_api_requires(Permissions.incident_rules_read)
def test_rule(identifier):
    try:
        rule = rules_get(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    payload = request.get_json() or {}
    sample_days = payload.get('sample_days', 7)
    limit = payload.get('limit', 50)
    matches = rule_dry_run(rule, sample_days=sample_days, limit=limit)
    return response_api_success({
        'rule_id': rule.rule_id,
        'matching_alert_ids': matches,
        'sample_days': sample_days,
    })


@incident_rules_blueprint.post('/<int:identifier>/backfill')
@ac_api_requires(Permissions.incident_rules_write)
def backfill(identifier):
    """Apply this rule's action to *historical* alerts. Alerts already
    grouped into an incident are skipped so the rule can't hijack an
    analyst's manual grouping. The dedupe / time-window logic keeps the
    operation idempotent — re-running produces no duplicates."""
    try:
        rule = rules_get(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    payload = request.get_json() or {}
    sample_days = payload.get('sample_days', 30)
    result = backfill_rule(rule, sample_days=sample_days)
    return response_api_success({'rule_id': rule.rule_id, **result})
