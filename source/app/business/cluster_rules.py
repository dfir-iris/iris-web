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

import hashlib
from datetime import datetime
from datetime import timedelta
from typing import List
from typing import Optional

from app.business.access_controls import access_controls_user_accessible_customers
from app.business.access_controls import access_controls_user_has_customer_scope
from app.business.alert_clusters import alert_cluster_open_matching
from app.datamgmt.filtering import apply_custom_conditions
from app.datamgmt.filtering import combine_conditions
from app.db import db
from app.iris_engine.utils.tracker import track_activity
from app.logger import logger
from app.models.alerts import Alert
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.cluster_rules import ClusterRule
from app.models.cluster_rules import RULE_ACTION_CREATE_CLUSTER
from app.models.alert_clusters import AlertCluster


# ---------------------------------------------------------------------------
# CRUD
#
# Every getter that a route calls must be gated by the caller's identity so
# a request from tenant A can never touch a rule scoped to tenant B — see
# `access_controls_user_has_customer_scope` for the exact semantics. The
# raw helpers (used internally by the evaluator, which runs in a Celery
# worker with no request context) live under the `_unchecked` suffix and
# MUST NOT be called from route handlers.
# ---------------------------------------------------------------------------

def _rules_get_unchecked(identifier: int) -> ClusterRule:
    rule = ClusterRule.query.filter_by(rule_id=identifier).first()
    if not rule:
        raise ObjectNotFoundError()
    return rule


def rules_create(user, permissions, rule: ClusterRule,
                 fallback_customer_access=None) -> ClusterRule:
    """Persist a new rule after verifying the caller can act on every
    customer the rule targets. A caller trying to create a rule scoped to
    a tenant they can't see (or a null-scope global rule without
    server_administrator) is rejected — otherwise `cluster_rules_write`
    would double as customer-elevation."""
    if not access_controls_user_has_customer_scope(
        user, permissions, rule.rule_customer_scope,
        fallback_customer_access=fallback_customer_access,
    ):
        raise BusinessProcessingError(
            'You do not have access to every customer in rule_customer_scope '
            '(or the rule is global and you are not a server administrator).'
        )
    db.session.add(rule)
    db.session.commit()
    track_activity(f'created cluster rule "{rule.rule_name}"')
    return rule


def rules_get(user, permissions, identifier: int,
              fallback_customer_access=None) -> ClusterRule:
    """Fetch a rule + verify the caller has access to it. Raises
    `ObjectNotFoundError` rather than a distinct forbidden error so a
    caller can't enumerate rule ids across tenants by watching for a
    403-vs-404 difference."""
    rule = _rules_get_unchecked(identifier)
    if not access_controls_user_has_customer_scope(
        user, permissions, rule.rule_customer_scope,
        fallback_customer_access=fallback_customer_access,
    ):
        raise ObjectNotFoundError()
    return rule


def rules_list(user, permissions) -> List[ClusterRule]:
    """List rules visible to the caller.

      * `server_administrator` sees every rule (null-scope + all tenants).
      * Everyone else sees only rules whose `rule_customer_scope` is a
        subset of the customers they have access to. Null-scope (global)
        rules are hidden from non-admins because acting on them would
        cross every tenant boundary.

    Ordering matches the evaluator so the UI reads in the same order the
    engine would fire them."""
    accessible = access_controls_user_accessible_customers(user, permissions)
    query = ClusterRule.query.order_by(
        ClusterRule.rule_priority.asc(), ClusterRule.rule_id.asc()
    )
    if accessible is None:  # server_administrator
        return query.all()
    rows = query.all()
    return [
        r for r in rows
        if r.rule_customer_scope is not None
        and r.rule_customer_scope
        and set(r.rule_customer_scope).issubset(accessible)
    ]


def rules_update(user, permissions, rule: ClusterRule, changes: dict,
                 fallback_customer_access=None) -> ClusterRule:
    """Apply `changes` after verifying the caller can act on both the
    rule's *current* scope AND its *incoming* scope. Skipping either
    check would let a caller who can only see tenant A pivot a rule
    from A → B (or vice versa) as a smuggling primitive."""
    # Current scope
    if not access_controls_user_has_customer_scope(
        user, permissions, rule.rule_customer_scope,
        fallback_customer_access=fallback_customer_access,
    ):
        raise ObjectNotFoundError()
    # Incoming scope — only check if the payload tried to change it.
    if 'rule_customer_scope' in changes:
        if not access_controls_user_has_customer_scope(
            user, permissions, changes['rule_customer_scope'],
            fallback_customer_access=fallback_customer_access,
        ):
            raise BusinessProcessingError(
                'You do not have access to every customer in the new rule_customer_scope.'
            )
    for key, value in changes.items():
        setattr(rule, key, value)
    rule.rule_updated_at = datetime.utcnow()
    db.session.commit()
    track_activity(f'updated cluster rule "{rule.rule_name}"')
    return rule


def rules_delete(rule: ClusterRule) -> None:
    """Delete a rule. Caller-scope check is done by whichever getter
    fetched `rule` — routes must load rules through `rules_get(user, ...)`
    before delete."""
    name = rule.rule_name
    db.session.delete(rule)
    db.session.commit()
    track_activity(f'deleted cluster rule "{name}"')


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _rule_matches_alert(rule: ClusterRule, alert_id: int) -> bool:
    """A rule matches when there exists exactly one Alert row whose PK is
    `alert_id` and that also satisfies `rule.rule_conditions`. We reuse
    `apply_custom_conditions` — the exact code path that already backs
    the alerts search filter — so the DSL semantics never diverge from
    what users see in the alert search UI."""
    conditions_payload = rule.rule_conditions or {}
    condition_list = conditions_payload.get('conditions') or []
    logic = conditions_payload.get('logic', 'and')

    query = Alert.query.filter(Alert.alert_id == alert_id)
    try:
        query, extra = apply_custom_conditions(query, Alert, condition_list)
    except Exception as exc:
        logger.warning(f'Rule #{rule.rule_id} has invalid conditions: {exc}')
        return False
    combined = combine_conditions(extra, logic)
    if combined is not None:
        query = query.filter(combined)
    return db.session.query(query.exists()).scalar()


def _dedupe_key(alert: Alert, rule: ClusterRule) -> str:
    """Deterministic key from the rule's `group_by` fields on the alert plus
    the rule id and a time bucket. Alerts landing in the same bucket + same
    group values stack into one cluster; the bucket rolls forward with
    `time_window_seconds` so the cluster stops accepting new alerts once
    the window closes."""
    conditions_payload = rule.rule_conditions or {}
    group_by = conditions_payload.get('group_by') or []
    time_window = conditions_payload.get('time_window_seconds')

    key_parts = [str(rule.rule_id)]
    for field in group_by:
        key_parts.append(f'{field}={getattr(alert, field, None)}')
    if time_window and time_window > 0:
        now = datetime.utcnow()
        bucket = int(now.timestamp() // time_window)
        key_parts.append(f'bucket={bucket}')
    raw = '|'.join(key_parts)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _apply_create_cluster(rule: ClusterRule, alert: Alert) -> Optional[AlertCluster]:
    config = rule.rule_action_config or {}
    dedupe_key = _dedupe_key(alert, rule)
    existing = alert_cluster_open_matching(alert.alert_customer_id, dedupe_key)
    if existing is not None:
        if alert.alert_id not in {a.alert_id for a in existing.alerts}:
            existing.alerts.append(alert)
            db.session.commit()
        return existing

    title_template = config.get('title_template') or f'Auto-created by rule: {rule.rule_name}'
    title = title_template.replace('{alert_title}', alert.alert_title or '')
    cluster = AlertCluster(
        cluster_title=title[:2048],
        cluster_description=config.get('description'),
        cluster_customer_id=alert.alert_customer_id,
        cluster_severity_id=alert.alert_severity_id,
        cluster_source_rule_id=rule.rule_id,
        cluster_dedupe_key=dedupe_key,
        cluster_creation_time=datetime.utcnow(),
    )
    # Deferred import to avoid a cycle at module import time. Public
    # names (no leading underscore) so Ruff doesn't flag cross-module
    # private imports.
    from app.business.alert_clusters import CLUSTER_STATUS_OPEN, resolve_status_id
    cluster.cluster_status_id = resolve_status_id(CLUSTER_STATUS_OPEN)
    db.session.add(cluster)
    db.session.flush()
    cluster.alerts.append(alert)
    db.session.commit()
    return cluster


def evaluate_rules_for_alert(alert_id: int) -> dict:
    """Load the alert fresh from the DB (this runs in a Celery worker with
    its own session), find every active rule whose customer scope covers
    the alert's tenant, and apply matches in priority order. Returns a small
    summary useful for logging and the /test endpoint."""
    alert = Alert.query.filter_by(alert_id=alert_id).first()
    if alert is None:
        return {'alert_id': alert_id, 'matched_rules': [], 'skipped': 'alert_not_found'}

    candidates = ClusterRule.query.filter(
        ClusterRule.rule_is_active.is_(True)
    ).order_by(
        ClusterRule.rule_priority.asc(), ClusterRule.rule_id.asc()
    ).all()

    applied = []
    for rule in candidates:
        scope = rule.rule_customer_scope
        if scope is not None and alert.alert_customer_id not in (scope or []):
            continue
        if not _rule_matches_alert(rule, alert.alert_id):
            continue
        try:
            if rule.rule_action_type == RULE_ACTION_CREATE_CLUSTER:
                cluster = _apply_create_cluster(rule, alert)
                applied.append({
                    'rule_id': rule.rule_id,
                    'action': RULE_ACTION_CREATE_CLUSTER,
                    'cluster_id': cluster.cluster_id if cluster else None,
                })
            # Flow attachment lives in the flow evaluator — see
            # `app.business.investigation_flows.evaluate_flows_for_alert`.
            # Rules no longer carry an `attach_flow` action.
        except Exception as exc:
            db.session.rollback()
            logger.exception(f'Failed to apply rule #{rule.rule_id} to alert #{alert_id}: {exc}')
    return {'alert_id': alert_id, 'matched_rules': applied}


def rule_dry_run(rule: ClusterRule, sample_days: int = 7, limit: int = 50) -> List[int]:
    """Return alert IDs that would match this rule against the last N days
    of alerts. Used by the settings UI to preview a rule before saving it.
    Read-only; does not run the actions."""
    since = datetime.utcnow() - timedelta(days=max(1, sample_days))
    conditions_payload = rule.rule_conditions or {}
    condition_list = conditions_payload.get('conditions') or []
    logic = conditions_payload.get('logic', 'and')

    query = Alert.query.filter(Alert.alert_creation_time >= since)
    scope = rule.rule_customer_scope
    if scope is not None:
        query = query.filter(Alert.alert_customer_id.in_(scope or [0]))
    try:
        query, extra = apply_custom_conditions(query, Alert, condition_list)
    except Exception as exc:
        logger.warning(f'Dry-run for rule #{rule.rule_id} failed to compile: {exc}')
        return []
    combined = combine_conditions(extra, logic)
    if combined is not None:
        query = query.filter(combined)
    rows = query.order_by(Alert.alert_creation_time.desc()).limit(limit).all()
    return [r.alert_id for r in rows]


def backfill_rule(rule: ClusterRule, sample_days: int = 30) -> dict:
    """Apply this rule's `create_cluster` action to *historical* alerts —
    matching alerts from the last `sample_days` days that aren't already
    attached to the cluster this rule would create. The dedupe key /
    time-window logic in `_apply_create_cluster` makes this naturally
    idempotent — re-running the same back-fill won't produce duplicate
    clusters.

    Skips alerts that are already members of ANY cluster to avoid
    dragging an analyst's manually-curated grouping under a rule they
    didn't consent to. Returns per-outcome counts for the UI toast.
    """
    if rule.rule_action_type != RULE_ACTION_CREATE_CLUSTER:
        return {'attached': 0, 'skipped_already_in_cluster': 0, 'errors': 0}

    since = datetime.utcnow() - timedelta(days=max(1, sample_days))
    conditions_payload = rule.rule_conditions or {}
    condition_list = conditions_payload.get('conditions') or []
    logic = conditions_payload.get('logic', 'and')

    query = Alert.query.filter(Alert.alert_creation_time >= since)
    scope = rule.rule_customer_scope
    if scope is not None:
        query = query.filter(Alert.alert_customer_id.in_(scope or [0]))
    try:
        query, extra = apply_custom_conditions(query, Alert, condition_list)
    except Exception as exc:
        logger.warning(f'Back-fill for rule #{rule.rule_id} failed to compile: {exc}')
        return {'attached': 0, 'skipped_already_in_cluster': 0, 'errors': 1}
    combined = combine_conditions(extra, logic)
    if combined is not None:
        query = query.filter(combined)

    attached = 0
    skipped = 0
    errors = 0
    # Materialise once — the create-cluster action commits, which
    # would otherwise invalidate a streaming query cursor mid-iteration.
    matches = query.order_by(Alert.alert_creation_time.asc()).all()
    for alert in matches:
        # Respect analyst intent: leave alerts alone if they're already
        # grouped into a cluster (manually or by an earlier rule).
        if alert.clusters:
            skipped += 1
            continue
        try:
            _apply_create_cluster(rule, alert)
            attached += 1
        except Exception as exc:
            db.session.rollback()
            logger.exception(
                f'Back-fill for rule #{rule.rule_id} failed on alert #{alert.alert_id}: {exc}'
            )
            errors += 1
    return {
        'attached': attached,
        'skipped_already_in_cluster': skipped,
        'errors': errors,
        'considered': len(matches),
    }
