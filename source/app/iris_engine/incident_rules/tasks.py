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

"""Async evaluation of incident-stacking rules AND investigation-flow
attachment for newly created / updated alerts and incidents.

Two orchestration steps per alert event:
  1. Evaluate incident rules — may stack this alert into an incident.
  2. Evaluate investigation flows — attaches a flow to the alert if any
     flow's own `flow_conditions` match. If step (1) stacked the alert
     into a fresh incident, we also fire flow evaluation for the
     incident so its own attachment gets computed right away rather
     than waiting for the next incident touch.

The task is intentionally thin — every decision lives in the business
layer. Celery is just for running this off the request path and for
retrying on transient DB errors.
"""

import logging

from sqlalchemy.exc import OperationalError

from app import celery


logger = logging.getLogger(__name__)


@celery.task(
    bind=True,
    name='iris.incident_rules.evaluate_alert',
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def evaluate_alert_rules(self, alert_id: int) -> dict:
    """Evaluate incident rules AND investigation flows for `alert_id`.

    Rules run first (may stack the alert into an incident); flows run
    second on the alert. If the rules created a fresh incident, we also
    kick off flow evaluation on that incident so both attachments settle
    within a single task cycle."""
    from app.business.incident_rules import evaluate_rules_for_alert
    from app.business.investigation_flows import evaluate_flows_for_alert
    from app.business.investigation_flows import evaluate_flows_for_incident
    from app.db import db

    try:
        rules_result = evaluate_rules_for_alert(alert_id)
        flow_id = evaluate_flows_for_alert(alert_id)
        # If any rule opened / attached to an incident, evaluate flows
        # on it too — a new incident should get its own flow decided
        # right away, not on the next touch.
        touched_incident_ids = {
            entry.get('incident_id')
            for entry in rules_result.get('matched_rules', [])
            if entry.get('action') == 'create_incident' and entry.get('incident_id')
        }
        incident_flow_attachments = {}
        for iid in touched_incident_ids:
            attached = evaluate_flows_for_incident(iid)
            if attached is not None:
                incident_flow_attachments[iid] = attached

        result = {
            **rules_result,
            'flow_attached_to_alert': flow_id,
            'flow_attached_to_incidents': incident_flow_attachments,
        }
        logger.debug('evaluate_alert_rules(%s) → %s', alert_id, result)
        return result
    except OperationalError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        logger.exception('evaluate_alert_rules(%s) failed', alert_id)
        return {'alert_id': alert_id, 'error': 'internal_error'}


@celery.task(
    bind=True,
    name='iris.investigation_flows.evaluate_incident',
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def evaluate_incident_flows(self, incident_id: int) -> dict:
    """Evaluate investigation flows for `incident_id`. Fired when an
    incident is created manually or its metadata is updated in a way
    that could affect matching (title/description/severity/etc.)."""
    from app.business.investigation_flows import evaluate_flows_for_incident
    from app.db import db

    try:
        flow_id = evaluate_flows_for_incident(incident_id)
        return {'incident_id': incident_id, 'flow_attached': flow_id}
    except OperationalError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        logger.exception('evaluate_incident_flows(%s) failed', incident_id)
        return {'incident_id': incident_id, 'error': 'internal_error'}
