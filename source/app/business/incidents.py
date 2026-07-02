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
from typing import Iterable
from typing import List
from typing import Optional

from app.business.access_controls import access_controls_user_has_customer_access
from app.datamgmt.alerts.alerts_db import create_case_from_alerts
from app.db import db
from app.iris_engine.utils.tracker import track_activity
from app.models.alerts import Alert
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.incidents import Incident
from app.models.incidents import IncidentStatus


# Public status-name constants. Kept as module-level names so callers
# in other modules can reference them without either duplicating the
# literal string (drift risk) or reaching into an underscored private
# (lint violation). The `_STATUS_*` aliases below are kept for the
# in-file callers.
INCIDENT_STATUS_OPEN = 'Open'
INCIDENT_STATUS_INVESTIGATING = 'Investigating'
INCIDENT_STATUS_DISMISSED = 'Dismissed'
INCIDENT_STATUS_ESCALATED = 'Escalated'

_STATUS_OPEN = INCIDENT_STATUS_OPEN
_STATUS_INVESTIGATING = INCIDENT_STATUS_INVESTIGATING
_STATUS_DISMISSED = INCIDENT_STATUS_DISMISSED
_STATUS_ESCALATED = INCIDENT_STATUS_ESCALATED


def resolve_status_id(status_name: str) -> int:
    """Look up an `IncidentStatus.status_id` by its human-readable name.

    Public so other business modules (e.g. `incident_rules._apply_create_incident`)
    can resolve the "Open" status when opening a new incident, without
    reaching into a private helper — Ruff / import-linters flag cross-
    module private imports and the underscore signals module-internal
    intent."""
    status = IncidentStatus.query.filter_by(status_name=status_name).first()
    if not status:
        raise BusinessProcessingError(f'IncidentStatus "{status_name}" is not seeded')
    return status.status_id


# Backwards-compatible alias — this file's own callers used `_status_id`
# before the rename; keep the alias so no in-file caller changes.
_status_id = resolve_status_id


def incidents_create(incident: Incident) -> Incident:
    if incident.incident_status_id is None:
        incident.incident_status_id = _status_id(_STATUS_OPEN)
    incident.incident_creation_time = datetime.utcnow()
    db.session.add(incident)
    db.session.commit()
    track_activity(f'created incident #{incident.incident_id} - {incident.incident_title}', ctx_less=True)
    _enqueue_flow_evaluation(incident.incident_id)
    return incident


def _enqueue_flow_evaluation(incident_id: int) -> None:
    """Fire the async flow evaluator against a newly created / updated
    incident. Import is deferred and errors are swallowed — a broken
    worker must not block incident writes on the request path."""
    try:
        from app.iris_engine.incident_rules.tasks import evaluate_incident_flows
        evaluate_incident_flows.delay(incident_id)
    except Exception:  # noqa: BLE001
        from app.logger import logger
        logger.exception('Failed to enqueue flow evaluation for incident #%s', incident_id)


def incidents_get(user, permissions, identifier, fallback_customer_access=None) -> Incident:
    incident = Incident.query.filter_by(incident_id=identifier).first()
    if not incident:
        raise ObjectNotFoundError()
    if not access_controls_user_has_customer_access(
        user, permissions, incident.incident_customer_id,
        fallback_customer_access=fallback_customer_access
    ):
        raise ObjectNotFoundError()
    return incident


def incidents_search(customer_id: Optional[int], status_id: Optional[int],
                     title: Optional[str], user_identifier_filter: Optional[int],
                     page: int, per_page: int, sort: Optional[str]):
    """Paginated incident search. `user_identifier_filter` = None means
    server-admin (see all). Otherwise scope by the caller's UserClient rows —
    same pattern `get_filtered_alerts` uses for tenant isolation."""
    from app.models.authorization import UserClient  # local import to avoid cycles

    query = Incident.query
    if user_identifier_filter is not None:
        accessible = db.session.query(UserClient.client_id).filter(
            UserClient.user_id == user_identifier_filter
        ).subquery()
        query = query.filter(Incident.incident_customer_id.in_(accessible))
    if customer_id is not None:
        query = query.filter(Incident.incident_customer_id == customer_id)
    if status_id is not None:
        query = query.filter(Incident.incident_status_id == status_id)
    if title:
        query = query.filter(Incident.incident_title.ilike(f'%{title}%'))

    direction = 'desc'
    if sort and sort.endswith(' asc'):
        direction = 'asc'
    if direction == 'asc':
        query = query.order_by(Incident.incident_creation_time.asc())
    else:
        query = query.order_by(Incident.incident_creation_time.desc())

    return query.paginate(page=page, per_page=per_page, error_out=False)


def incidents_update(incident: Incident, changes: dict) -> Incident:
    for key, value in changes.items():
        setattr(incident, key, value)
    db.session.commit()
    track_activity(f'updated incident #{incident.incident_id}', ctx_less=True)
    _enqueue_flow_evaluation(incident.incident_id)
    return incident


def incidents_delete(incident: Incident) -> None:
    identifier = incident.incident_id
    db.session.delete(incident)
    db.session.commit()
    track_activity(f'deleted incident #{identifier}', ctx_less=True)


def incident_add_alerts(incident: Incident, alert_ids: Iterable[int]) -> Incident:
    """Attach alerts to an incident. Silently skips alerts already attached and
    alerts belonging to a different customer than the incident — mixing tenants
    inside a container would leak data through `incident.alerts`."""
    ids = list(alert_ids)
    if not ids:
        return incident
    alerts = Alert.query.filter(
        Alert.alert_id.in_(ids),
        Alert.alert_customer_id == incident.incident_customer_id
    ).all()
    existing = {a.alert_id for a in incident.alerts}
    for alert in alerts:
        if alert.alert_id not in existing:
            incident.alerts.append(alert)
    db.session.commit()
    return incident


def incident_remove_alert(incident: Incident, alert_id: int) -> Incident:
    incident.alerts = [a for a in incident.alerts if a.alert_id != alert_id]
    db.session.commit()
    return incident


def incident_escalate_to_case(incident: Incident, template_id: Optional[int] = None,
                              case_title: Optional[str] = None, note: Optional[str] = None,
                              import_as_event: bool = False, case_tags: str = ''):
    """Escalate the incident to a case. Reuses `create_case_from_alerts` so the
    case gets all member alerts linked (plus their IOCs/assets), which is what
    the existing alerts-to-case flow already does. Idempotent-ish: re-escalating
    a linked incident raises, callers should check `incident_case_id` first."""
    if incident.incident_case_id is not None:
        raise BusinessProcessingError('Incident already escalated to a case')
    if not incident.alerts:
        raise BusinessProcessingError('Cannot escalate an incident with no alerts')

    case = create_case_from_alerts(
        alerts=list(incident.alerts),
        iocs_list=[str(i.ioc_id) for a in incident.alerts for i in (a.iocs or [])],
        assets_list=[str(a2.asset_id) for a in incident.alerts for a2 in (a.assets or [])],
        case_title=case_title or incident.incident_title,
        note=note or incident.incident_description or '',
        import_as_event=import_as_event,
        case_tags=case_tags,
        template_id=template_id,
    )
    incident.incident_case_id = case.case_id
    incident.incident_status_id = _status_id(_STATUS_ESCALATED)
    db.session.commit()
    track_activity(
        f'escalated incident #{incident.incident_id} to case #{case.case_id}',
        ctx_less=True,
    )
    return case


def incident_open_matching(customer_id: int, dedupe_key: str) -> Optional[Incident]:
    """Look up an open incident with the given dedupe key for stacking. Used by
    the rules engine when a rule action is create_incident and its dedupe key
    matches an incident already accepting alerts."""
    if not dedupe_key:
        return None
    open_status_id = _status_id(_STATUS_OPEN)
    investigating_status_id = _status_id(_STATUS_INVESTIGATING)
    return Incident.query.filter(
        Incident.incident_customer_id == customer_id,
        Incident.incident_dedupe_key == dedupe_key,
        Incident.incident_status_id.in_([open_status_id, investigating_status_id]),
    ).order_by(Incident.incident_creation_time.desc()).first()
