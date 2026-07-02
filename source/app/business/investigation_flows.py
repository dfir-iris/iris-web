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

from app.datamgmt.filtering import apply_custom_conditions
from app.datamgmt.filtering import combine_conditions
from app.db import db
from app.iris_engine.utils.tracker import track_activity
from app.logger import logger
from app.models.alerts import Alert
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.incidents import Incident
from app.models.investigation_flows import AlertInvestigationProgress
from app.models.investigation_flows import FLOW_TARGET_ALERT
from app.models.investigation_flows import FLOW_TARGET_BOTH
from app.models.investigation_flows import FLOW_TARGET_INCIDENT
from app.models.investigation_flows import IncidentInvestigationProgress
from app.models.investigation_flows import InvestigationFlow
from app.models.investigation_flows import InvestigationFlowStep


def flows_create(flow: InvestigationFlow) -> InvestigationFlow:
    db.session.add(flow)
    db.session.commit()
    track_activity(f'created investigation flow #{flow.flow_id} - {flow.flow_name}', ctx_less=True)
    return flow


def flows_list(customer_id: Optional[int] = None) -> List[InvestigationFlow]:
    """Return active flows visible for a customer. `customer_id=None` returns
    all active flows (settings admin view). A flow is visible when its
    `flow_customer_scope` is null (all customers) or contains `customer_id`."""
    query = InvestigationFlow.query.filter(InvestigationFlow.flow_is_active.is_(True))
    if customer_id is None:
        return query.order_by(InvestigationFlow.flow_name.asc()).all()
    rows = query.order_by(InvestigationFlow.flow_name.asc()).all()
    return [f for f in rows
            if f.flow_customer_scope is None or customer_id in (f.flow_customer_scope or [])]


def flows_get(identifier: int) -> InvestigationFlow:
    flow = InvestigationFlow.query.filter_by(flow_id=identifier).first()
    if not flow:
        raise ObjectNotFoundError()
    return flow


def flows_update(flow: InvestigationFlow, changes: dict) -> InvestigationFlow:
    for key, value in changes.items():
        if key == 'steps':
            continue  # steps mutated via separate endpoints
        setattr(flow, key, value)
    flow.flow_updated_at = datetime.utcnow()
    db.session.commit()
    return flow


def flows_delete(flow: InvestigationFlow) -> None:
    identifier = flow.flow_id
    db.session.delete(flow)
    db.session.commit()
    track_activity(f'deleted investigation flow #{identifier}', ctx_less=True)


def flow_step_create(flow: InvestigationFlow, step: InvestigationFlowStep) -> InvestigationFlowStep:
    step.flow_id = flow.flow_id
    db.session.add(step)
    db.session.commit()
    return step


def flow_step_get(step_id: int) -> InvestigationFlowStep:
    step = InvestigationFlowStep.query.filter_by(step_id=step_id).first()
    if not step:
        raise ObjectNotFoundError()
    return step


def flow_step_update(step: InvestigationFlowStep, changes: dict) -> InvestigationFlowStep:
    for key, value in changes.items():
        setattr(step, key, value)
    db.session.commit()
    return step


def flow_step_delete(step: InvestigationFlowStep) -> None:
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
    step = flow_step_get(step_id)
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
# Incident progress (mirror of the alert progress helpers)
# ---------------------------------------------------------------------------

def incident_progress_list(incident: Incident) -> List[IncidentInvestigationProgress]:
    if not incident.incident_investigation_flow_id:
        return []
    return IncidentInvestigationProgress.query.filter_by(
        incident_id=incident.incident_id
    ).all()


def incident_progress_record(incident: Incident, step_id: int, user_id: int,
                             note: Optional[str] = None) -> IncidentInvestigationProgress:
    if not incident.incident_investigation_flow_id:
        raise BusinessProcessingError('Incident has no investigation flow attached')
    step = flow_step_get(step_id)
    if step.flow_id != incident.incident_investigation_flow_id:
        raise BusinessProcessingError("Step does not belong to the incident's flow")
    row = IncidentInvestigationProgress.query.filter_by(
        incident_id=incident.incident_id, step_id=step_id
    ).first()
    if row is None:
        row = IncidentInvestigationProgress(
            incident_id=incident.incident_id,
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


def incident_progress_uncheck(incident: Incident, step_id: int) -> None:
    row = IncidentInvestigationProgress.query.filter_by(
        incident_id=incident.incident_id, step_id=step_id
    ).first()
    if row is None:
        return
    db.session.delete(row)
    db.session.commit()


# ---------------------------------------------------------------------------
# Flow evaluator — decides which flow (if any) to attach to a given
# alert or incident, based on the flow's own `flow_conditions`.
# ---------------------------------------------------------------------------

def _flow_matches(flow: InvestigationFlow, model, entity_id: int) -> bool:
    """Return True when the given entity (Alert or Incident) satisfies the
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

    pk_col = model.alert_id if model is Alert else model.incident_id
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
    the given target ('alert' or 'incident'). Ordered by priority so the
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


def evaluate_flows_for_incident(incident_id: int) -> Optional[int]:
    incident = Incident.query.filter_by(incident_id=incident_id).first()
    if incident is None or incident.incident_investigation_flow_id is not None:
        return incident.incident_investigation_flow_id if incident else None
    for flow in _candidate_flows_for(FLOW_TARGET_INCIDENT, incident.incident_customer_id):
        if _flow_matches(flow, Incident, incident_id):
            incident.incident_investigation_flow_id = flow.flow_id
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
    """Back-fill this flow onto historical alerts and/or incidents whose
    FK is empty. Returns `(alerts_attached, incidents_attached)`.

    Only matches rows where no flow is already attached — we never
    overwrite an existing attachment because the analyst may have chosen
    it deliberately (or the pre-existing flow may already have progress
    check-offs against it that we'd orphan)."""
    alerts_attached = 0
    incidents_attached = 0
    if flow.flow_target in (FLOW_TARGET_ALERT, FLOW_TARGET_BOTH):
        alerts_attached = _deploy_flow_to_model(
            flow, Alert,
            Alert.alert_investigation_flow_id, Alert.alert_customer_id, Alert.alert_id,
        )
    if flow.flow_target in (FLOW_TARGET_INCIDENT, FLOW_TARGET_BOTH):
        incidents_attached = _deploy_flow_to_model(
            flow, Incident,
            Incident.incident_investigation_flow_id,
            Incident.incident_customer_id, Incident.incident_id,
        )
    track_activity(
        f'deployed flow #{flow.flow_id} — alerts={alerts_attached}, '
        f'incidents={incidents_attached}',
        ctx_less=True,
    )
    return alerts_attached, incidents_attached
