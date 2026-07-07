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

from datetime import datetime
from typing import List
from typing import Optional
from typing import Tuple

from app.business.access_controls import access_controls_user_accessible_customers
from app.business.access_controls import access_controls_user_has_customer_scope
from app.datamgmt.filtering import apply_custom_conditions
from app.datamgmt.filtering import combine_conditions
from app.db import db
from app.iris_engine.utils.tracker import track_activity
from app.logger import logger
from app.models.alerts import Alert
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.alert_clusters import AlertCluster
from app.models.investigation_flows import AlertClusterInvestigationProgress
from app.models.investigation_flows import AlertInvestigationProgress
from app.models.investigation_flows import FLOW_TARGET_ALERT
from app.models.investigation_flows import FLOW_TARGET_BOTH
from app.models.investigation_flows import FLOW_TARGET_CLUSTER
from app.models.investigation_flows import InvestigationFlow
from app.models.investigation_flows import InvestigationFlowStep


# ---------------------------------------------------------------------------
# CRUD
#
# Route handlers must call the scope-aware helpers below (that take
# `user`/`permissions`) — never the `_unchecked` variants. The
# `_unchecked` helpers exist for the Celery-worker code path (flow
# evaluator, deploy_flow) where there's no request context to derive
# a caller from.
# ---------------------------------------------------------------------------

def _flows_get_unchecked(identifier: int) -> InvestigationFlow:
    flow = InvestigationFlow.query.filter_by(flow_id=identifier).first()
    if not flow:
        raise ObjectNotFoundError()
    return flow


def _flow_step_get_unchecked(step_id: int) -> InvestigationFlowStep:
    step = InvestigationFlowStep.query.filter_by(step_id=step_id).first()
    if not step:
        raise ObjectNotFoundError()
    return step


def flows_create(user, permissions, flow: InvestigationFlow,
                 fallback_customer_access=None) -> InvestigationFlow:
    """Persist a new flow after verifying the caller can act on every
    customer the flow declares in `flow_customer_scope`. Global (null)
    scope requires `server_administrator` — otherwise `investigation_flows_write`
    would suffice to attach a flow to every tenant on the box."""
    if not access_controls_user_has_customer_scope(
        user, permissions, flow.flow_customer_scope,
        fallback_customer_access=fallback_customer_access,
    ):
        raise BusinessProcessingError(
            'You do not have access to every customer in flow_customer_scope '
            '(or the flow is global and you are not a server administrator).'
        )
    db.session.add(flow)
    db.session.commit()
    track_activity(f'created investigation flow #{flow.flow_id} - {flow.flow_name}', ctx_less=True)
    return flow


def flows_list(user, permissions) -> List[InvestigationFlow]:
    """List active flows visible to the caller.

    Semantics match `rules_list`:
      * `server_administrator` sees every flow.
      * Everyone else sees flows whose `flow_customer_scope` is a subset
        of their accessible customers. Null-scope flows are hidden from
        non-admins.
    """
    accessible = access_controls_user_accessible_customers(user, permissions)
    query = InvestigationFlow.query.filter(
        InvestigationFlow.flow_is_active.is_(True)
    ).order_by(InvestigationFlow.flow_name.asc())
    if accessible is None:
        return query.all()
    rows = query.all()
    return [
        f for f in rows
        if f.flow_customer_scope is not None
        and f.flow_customer_scope
        and set(f.flow_customer_scope).issubset(accessible)
    ]


def flows_get(user, permissions, identifier: int,
              fallback_customer_access=None) -> InvestigationFlow:
    """Fetch a flow + gate by caller's scope. `ObjectNotFoundError` on
    lack of access — same "no side-channel enumeration" pattern as the
    rules helpers."""
    flow = _flows_get_unchecked(identifier)
    if not access_controls_user_has_customer_scope(
        user, permissions, flow.flow_customer_scope,
        fallback_customer_access=fallback_customer_access,
    ):
        raise ObjectNotFoundError()
    return flow


def flows_update(user, permissions, flow: InvestigationFlow, changes: dict,
                 fallback_customer_access=None) -> InvestigationFlow:
    """Apply `changes` after checking both current and incoming scope.
    Refusing the update when either side is unreachable prevents a caller
    from pivoting a flow between tenants."""
    if not access_controls_user_has_customer_scope(
        user, permissions, flow.flow_customer_scope,
        fallback_customer_access=fallback_customer_access,
    ):
        raise ObjectNotFoundError()
    if 'flow_customer_scope' in changes:
        if not access_controls_user_has_customer_scope(
            user, permissions, changes['flow_customer_scope'],
            fallback_customer_access=fallback_customer_access,
        ):
            raise BusinessProcessingError(
                'You do not have access to every customer in the new flow_customer_scope.'
            )
    for key, value in changes.items():
        if key == 'steps':
            continue  # steps mutated via separate endpoints
        setattr(flow, key, value)
    flow.flow_updated_at = datetime.utcnow()
    db.session.commit()
    return flow


def flows_delete(flow: InvestigationFlow) -> None:
    """Delete a flow. Caller-scope check is done by the getter that
    loaded `flow` — routes MUST load flows through `flows_get(user, ...)`
    before delete."""
    identifier = flow.flow_id
    db.session.delete(flow)
    db.session.commit()
    track_activity(f'deleted investigation flow #{identifier}', ctx_less=True)


def flow_step_create(flow: InvestigationFlow, step: InvestigationFlowStep) -> InvestigationFlowStep:
    """Attach a step to `flow`. Route MUST have loaded `flow` via
    `flows_get(user, ...)` so the caller-scope check has already run —
    otherwise a caller could `POST /investigation-flows/<other-tenant-id>/steps`
    to seed steps on a flow they can't see."""
    step.flow_id = flow.flow_id
    db.session.add(step)
    db.session.commit()
    return step


def flow_step_get(user, permissions, step_id: int,
                  fallback_customer_access=None) -> InvestigationFlowStep:
    """Fetch a step + verify the caller has access to the parent flow.
    Same 404-on-no-access pattern to avoid step-id enumeration."""
    step = _flow_step_get_unchecked(step_id)
    parent = _flows_get_unchecked(step.flow_id)
    if not access_controls_user_has_customer_scope(
        user, permissions, parent.flow_customer_scope,
        fallback_customer_access=fallback_customer_access,
    ):
        raise ObjectNotFoundError()
    return step


def flow_step_update(step: InvestigationFlowStep, changes: dict) -> InvestigationFlowStep:
    """Mutate a step. Route MUST have loaded `step` via
    `flow_step_get(user, ...)`."""
    for key, value in changes.items():
        setattr(step, key, value)
    db.session.commit()
    return step


def flow_step_delete(step: InvestigationFlowStep) -> None:
    """Delete a step. Route MUST have loaded `step` via
    `flow_step_get(user, ...)`."""
    db.session.delete(step)
    db.session.commit()


def alert_progress_list(alert: Alert) -> List[AlertInvestigationProgress]:
    if not alert.alert_investigation_flow_id:
        return []
    return AlertInvestigationProgress.query.filter_by(alert_id=alert.alert_id).all()


def alert_progress_record(alert: Alert, step_id: int, user_id: int,
                          note: Optional[str] = None) -> AlertInvestigationProgress:
    """Idempotent: re-checking the same step just updates the note + timestamp."""
    if not alert.alert_investigation_flow_id:
        raise BusinessProcessingError('Alert has no investigation flow attached')
    # Caller-scope was already enforced when the Alert/AlertCluster was
    # loaded upstream; the step lookup here is a data-integrity check
    # (step must belong to the entity's attached flow), so the unchecked
    # variant is correct.
    step = _flow_step_get_unchecked(step_id)
    if step.flow_id != alert.alert_investigation_flow_id:
        raise BusinessProcessingError('Step does not belong to the alert\'s flow')
    row = AlertInvestigationProgress.query.filter_by(
        alert_id=alert.alert_id, step_id=step_id
    ).first()
    if row is None:
        row = AlertInvestigationProgress(
            alert_id=alert.alert_id,
            step_id=step_id,
            completed_by_user_id=user_id,
            note=note,
        )
        db.session.add(row)
    else:
        row.completed_by_user_id = user_id
        row.completed_at = datetime.utcnow()
        if note is not None:
            row.note = note
    db.session.commit()
    return row


def alert_progress_uncheck(alert: Alert, step_id: int) -> None:
    row = AlertInvestigationProgress.query.filter_by(
        alert_id=alert.alert_id, step_id=step_id
    ).first()
    if row is None:
        return
    db.session.delete(row)
    db.session.commit()


# ---------------------------------------------------------------------------
# Alert-cluster progress (mirror of the alert progress helpers)
# ---------------------------------------------------------------------------

def alert_cluster_progress_list(cluster: AlertCluster) -> List[AlertClusterInvestigationProgress]:
    if not cluster.cluster_investigation_flow_id:
        return []
    return AlertClusterInvestigationProgress.query.filter_by(
        cluster_id=cluster.cluster_id
    ).all()


def alert_cluster_progress_record(cluster: AlertCluster, step_id: int, user_id: int,
                                  note: Optional[str] = None) -> AlertClusterInvestigationProgress:
    if not cluster.cluster_investigation_flow_id:
        raise BusinessProcessingError('Alert cluster has no investigation flow attached')
    # Caller-scope was already enforced when the Alert/AlertCluster was
    # loaded upstream; the step lookup here is a data-integrity check
    # (step must belong to the entity's attached flow), so the unchecked
    # variant is correct.
    step = _flow_step_get_unchecked(step_id)
    if step.flow_id != cluster.cluster_investigation_flow_id:
        raise BusinessProcessingError("Step does not belong to the cluster's flow")
    row = AlertClusterInvestigationProgress.query.filter_by(
        cluster_id=cluster.cluster_id, step_id=step_id
    ).first()
    if row is None:
        row = AlertClusterInvestigationProgress(
            cluster_id=cluster.cluster_id,
            step_id=step_id,
            completed_by_user_id=user_id,
            note=note,
        )
        db.session.add(row)
    else:
        row.completed_by_user_id = user_id
        row.completed_at = datetime.utcnow()
        if note is not None:
            row.note = note
    db.session.commit()
    return row


def alert_cluster_progress_uncheck(cluster: AlertCluster, step_id: int) -> None:
    row = AlertClusterInvestigationProgress.query.filter_by(
        cluster_id=cluster.cluster_id, step_id=step_id
    ).first()
    if row is None:
        return
    db.session.delete(row)
    db.session.commit()


# ---------------------------------------------------------------------------
# Flow evaluator — decides which flow (if any) to attach to a given
# alert or alert cluster, based on the flow's own `flow_conditions`.
# ---------------------------------------------------------------------------

def _flow_matches(flow: InvestigationFlow, model, entity_id: int) -> bool:
    """Return True when the given entity (Alert or AlertCluster) satisfies the
    flow's conditions. Reuses `apply_custom_conditions` — same code path
    that backs the alert/case search filter — so the DSL never diverges
    from what users see when authoring conditions.

    A flow with no conditions never auto-attaches (guard callers).
    """
    conditions_payload = flow.flow_conditions or {}
    condition_list = conditions_payload.get('conditions') or []
    if not condition_list:
        return False
    logic = conditions_payload.get('logic', 'and')

    pk_col = model.alert_id if model is Alert else model.cluster_id
    query = model.query.filter(pk_col == entity_id)
    try:
        query, extra = apply_custom_conditions(query, model, condition_list)
    except Exception as exc:
        logger.warning(f'Flow #{flow.flow_id} has invalid conditions: {exc}')
        return False
    combined = combine_conditions(extra, logic)
    if combined is not None:
        query = query.filter(combined)
    return db.session.query(query.exists()).scalar()


def _candidate_flows_for(target: str, customer_id: int) -> List[InvestigationFlow]:
    """Active flows visible for `customer_id` whose `flow_target` accepts
    the given target ('alert' or 'alert_cluster'). Ordered by priority so the
    first match wins."""
    accepted = (target, FLOW_TARGET_BOTH)
    rows = InvestigationFlow.query.filter(
        InvestigationFlow.flow_is_active.is_(True),
        InvestigationFlow.flow_target.in_(accepted),
    ).order_by(
        InvestigationFlow.flow_priority.asc(),
        InvestigationFlow.flow_id.asc(),
    ).all()
    return [f for f in rows
            if f.flow_customer_scope is None or customer_id in (f.flow_customer_scope or [])]


def evaluate_flows_for_alert(alert_id: int) -> Optional[int]:
    """First-match-wins: assign `alert.alert_investigation_flow_id` to the
    first active alert-scoped flow whose conditions match. Idempotent —
    does nothing if a flow is already attached. Returns the attached
    flow_id, or None."""
    alert = Alert.query.filter_by(alert_id=alert_id).first()
    if alert is None or alert.alert_investigation_flow_id is not None:
        return alert.alert_investigation_flow_id if alert else None
    for flow in _candidate_flows_for(FLOW_TARGET_ALERT, alert.alert_customer_id):
        if _flow_matches(flow, Alert, alert_id):
            alert.alert_investigation_flow_id = flow.flow_id
            db.session.commit()
            return flow.flow_id
    return None


def evaluate_flows_for_alert_cluster(cluster_id: int) -> Optional[int]:
    cluster = AlertCluster.query.filter_by(cluster_id=cluster_id).first()
    if cluster is None or cluster.cluster_investigation_flow_id is not None:
        return cluster.cluster_investigation_flow_id if cluster else None
    for flow in _candidate_flows_for(FLOW_TARGET_CLUSTER, cluster.cluster_customer_id):
        if _flow_matches(flow, AlertCluster, cluster_id):
            cluster.cluster_investigation_flow_id = flow.flow_id
            db.session.commit()
            return flow.flow_id
    return None


# ---------------------------------------------------------------------------
# Deploy-to-existing — back-fill a flow onto historical entities that
# match its conditions and don't already have a flow attached.
# ---------------------------------------------------------------------------

def _deploy_flow_to_model(flow: InvestigationFlow, model, fk_col,
                          customer_col, pk_col) -> int:
    """Attach `flow` to every row of `model` whose FK column is NULL and
    whose conditions match the flow. Returns the row count attached.

    Scoped by the flow's own `flow_customer_scope` — a flow that lists
    customers must not back-fill onto tenants it can't see."""
    conditions_payload = flow.flow_conditions or {}
    condition_list = conditions_payload.get('conditions') or []
    if not condition_list:
        return 0
    logic = conditions_payload.get('logic', 'and')

    query = model.query.filter(fk_col.is_(None))
    if flow.flow_customer_scope:
        query = query.filter(customer_col.in_(flow.flow_customer_scope))
    try:
        query, extra = apply_custom_conditions(query, model, condition_list)
    except Exception as exc:
        logger.warning(f'Flow #{flow.flow_id} deploy failed to compile: {exc}')
        return 0
    combined = combine_conditions(extra, logic)
    if combined is not None:
        query = query.filter(combined)

    rows = query.all()
    for row in rows:
        setattr(row, fk_col.key, flow.flow_id)
    db.session.commit()
    return len(rows)


def deploy_flow(flow: InvestigationFlow) -> Tuple[int, int]:
    """Back-fill this flow onto historical alerts and/or alert clusters whose
    FK is empty. Returns `(alerts_attached, clusters_attached)`.

    Only matches rows where no flow is already attached — we never
    overwrite an existing attachment because the analyst may have chosen
    it deliberately (or the pre-existing flow may already have progress
    check-offs against it that we'd orphan)."""
    alerts_attached = 0
    clusters_attached = 0
    if flow.flow_target in (FLOW_TARGET_ALERT, FLOW_TARGET_BOTH):
        alerts_attached = _deploy_flow_to_model(
            flow, Alert,
            Alert.alert_investigation_flow_id, Alert.alert_customer_id, Alert.alert_id,
        )
    if flow.flow_target in (FLOW_TARGET_CLUSTER, FLOW_TARGET_BOTH):
        clusters_attached = _deploy_flow_to_model(
            flow, AlertCluster,
            AlertCluster.cluster_investigation_flow_id,
            AlertCluster.cluster_customer_id, AlertCluster.cluster_id,
        )
    track_activity(
        f'deployed flow #{flow.flow_id} — alerts={alerts_attached}, '
        f'clusters={clusters_attached}',
        ctx_less=True,
    )
    return alerts_attached, clusters_attached
