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

"""Async evaluation of cluster-stacking rules AND investigation-flow
attachment for newly created / updated alerts and alert clusters.

Two orchestration steps per alert event:
  1. Evaluate cluster rules — may stack this alert into a cluster.
  2. Evaluate investigation flows — attaches a flow to the alert if any
     flow's own `flow_conditions` match. If step (1) stacked the alert
     into a fresh cluster, we also fire flow evaluation for the
     cluster so its own attachment gets computed right away rather
     than waiting for the next cluster touch.

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
    name='iris.cluster_rules.evaluate_alert',
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def evaluate_alert_rules(self, alert_id: int) -> dict:
    """Evaluate cluster rules AND investigation flows for `alert_id`.

    Rules run first (may stack the alert into a cluster); flows run
    second on the alert. If the rules created a fresh cluster, we also
    kick off flow evaluation on that cluster so both attachments settle
    within a single task cycle."""
    from app.business.cluster_rules import evaluate_rules_for_alert
    from app.business.investigation_flows import evaluate_flows_for_alert
    from app.business.investigation_flows import evaluate_flows_for_alert_cluster
    from app.db import db

    try:
        rules_result = evaluate_rules_for_alert(alert_id)
        flow_id = evaluate_flows_for_alert(alert_id)
        # If any rule opened / attached to a cluster, evaluate flows
        # on it too — a new cluster should get its own flow decided
        # right away, not on the next touch.
        touched_cluster_ids = {
            entry.get('cluster_id')
            for entry in rules_result.get('matched_rules', [])
            if entry.get('action') == 'create_cluster' and entry.get('cluster_id')
        }
        cluster_flow_attachments = {}
        for cid in touched_cluster_ids:
            attached = evaluate_flows_for_alert_cluster(cid)
            if attached is not None:
                cluster_flow_attachments[cid] = attached

        result = {
            **rules_result,
            'flow_attached_to_alert': flow_id,
            'flow_attached_to_clusters': cluster_flow_attachments,
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
    name='iris.investigation_flows.evaluate_alert_cluster',
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def evaluate_alert_cluster_flows(self, cluster_id: int) -> dict:
    """Evaluate investigation flows for `cluster_id`. Fired when a
    cluster is created manually or its metadata is updated in a way
    that could affect matching (title/description/severity/etc.)."""
    from app.business.investigation_flows import evaluate_flows_for_alert_cluster
    from app.db import db

    try:
        flow_id = evaluate_flows_for_alert_cluster(cluster_id)
        return {'cluster_id': cluster_id, 'flow_attached': flow_id}
    except OperationalError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        logger.exception('evaluate_alert_cluster_flows(%s) failed', cluster_id)
        return {'cluster_id': cluster_id, 'error': 'internal_error'}
