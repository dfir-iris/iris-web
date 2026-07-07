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
from app.business.cluster_rules import backfill_rule
from app.business.cluster_rules import rule_dry_run
from app.business.cluster_rules import rules_create
from app.business.cluster_rules import rules_delete
from app.business.cluster_rules import rules_get
from app.business.cluster_rules import rules_list
from app.business.cluster_rules import rules_update
from app.models.authorization import Permissions
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.schema.marshables import ClusterRuleSchema


# Fields the caller must never be able to set / mutate via the request
# body — they carry audit / server-owned attribution and would otherwise
# let a caller spoof "created by <someone else>" or reassign a rule's
# ownership. `rule_id` / `rule_uuid` / `rule_created_at` are dropped for
# similar reasons (they're server-assigned identity / timestamps).
_RULE_READONLY_FIELDS = frozenset({
    'rule_id',
    'rule_uuid',
    'rule_created_by',
    'rule_created_at',
    'rule_updated_at',
})


def _strip_readonly(payload):
    if not isinstance(payload, dict):
        return payload
    return {k: v for k, v in payload.items() if k not in _RULE_READONLY_FIELDS}


def _caller():
    """Common `(user, permissions)` tuple that the business-layer scope
    helpers expect. Uses `ac_current_user_permissions_mask` — the public
    accessor over the underlying mask helper — so both session and
    API-key auth paths resolve to the caller's true permission mask.
    Reading `session['permissions']` directly would miss the API-key
    branch (permissions live on `flask.g` there)."""
    return iris_current_user, ac_current_user_permissions_mask()


cluster_rules_blueprint = Blueprint('cluster_rules_rest_v2', __name__, url_prefix='/cluster-rules')

_schema = ClusterRuleSchema()


@cluster_rules_blueprint.get('')
@ac_api_requires(Permissions.cluster_rules_read)
def list_rules():
    user, perms = _caller()
    rows = rules_list(user, perms)
    return response_api_success([_schema.dump(r) for r in rows])


@cluster_rules_blueprint.post('')
@ac_api_requires(Permissions.cluster_rules_write)
def create_rule():
    user, perms = _caller()
    payload = _strip_readonly(request.get_json() or {})
    # Server-owned attribution — set AFTER stripping any spoofed value
    # the client may have supplied.
    payload['rule_created_by'] = iris_current_user.id
    try:
        rule = _schema.load(payload)
    except ValidationError as exc:
        return response_api_error('Data error', data=exc.messages)
    try:
        result = rules_create(
            user, perms, rule,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except BusinessProcessingError as exc:
        return response_api_error(exc.get_message(), data=exc.get_data())
    return response_api_created(_schema.dump(result))


@cluster_rules_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.cluster_rules_read)
def read_rule(identifier):
    user, perms = _caller()
    try:
        rule = rules_get(
            user, perms, identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_schema.dump(rule))


@cluster_rules_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.cluster_rules_write)
def update_rule(identifier):
    user, perms = _caller()
    try:
        rule = rules_get(
            user, perms, identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    payload = _strip_readonly(request.get_json() or {})
    try:
        _schema.load(payload, instance=rule, partial=True)
    except ValidationError as exc:
        return response_api_error('Data error', data=exc.messages)
    try:
        result = rules_update(
            user, perms, rule, payload,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except BusinessProcessingError as exc:
        return response_api_error(exc.get_message(), data=exc.get_data())
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_schema.dump(result))


@cluster_rules_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.cluster_rules_write)
def delete_rule(identifier):
    user, perms = _caller()
    try:
        rule = rules_get(
            user, perms, identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    rules_delete(rule)
    return response_api_deleted()


@cluster_rules_blueprint.post('/<int:identifier>/test')
@ac_api_requires(Permissions.cluster_rules_read)
def test_rule(identifier):
    user, perms = _caller()
    try:
        rule = rules_get(
            user, perms, identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
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


@cluster_rules_blueprint.post('/<int:identifier>/backfill')
@ac_api_requires(Permissions.cluster_rules_write)
def backfill(identifier):
    """Apply this rule's action to *historical* alerts. Alerts already
    grouped into a cluster are skipped so the rule can't hijack an
    analyst's manual grouping. The dedupe / time-window logic keeps the
    operation idempotent — re-running produces no duplicates.

    Loaded through the scope-gated `rules_get` so a caller who can't
    see every tenant in `rule.rule_customer_scope` gets a 404 (matching
    the getter's behaviour) rather than a cross-tenant write."""
    user, perms = _caller()
    try:
        rule = rules_get(
            user, perms, identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    payload = request.get_json() or {}
    sample_days = payload.get('sample_days', 30)
    result = backfill_rule(rule, sample_days=sample_days)
    return response_api_success({'rule_id': rule.rule_id, **result})
