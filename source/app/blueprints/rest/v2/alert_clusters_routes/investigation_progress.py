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

"""Alert-cluster-scoped investigation-flow progress endpoints. Mirrors the
alert-scoped sub-blueprint (`alerts_routes/investigation_progress.py`)
so the frontend can render an identical checklist UI on both entities."""

from flask import Blueprint
from flask import request
from flask import session

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_current_user_has_customer_access
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.business.alert_clusters import alert_clusters_get
from app.business.investigation_flows import alert_cluster_progress_list
from app.business.investigation_flows import alert_cluster_progress_record
from app.business.investigation_flows import alert_cluster_progress_uncheck
from app.models.authorization import Permissions
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.schema.marshables import AlertClusterInvestigationProgressSchema


alert_clusters_investigation_progress_blueprint = Blueprint(
    'alert_clusters_investigation_progress_rest_v2', __name__
)

_schema = AlertClusterInvestigationProgressSchema()


def _load_cluster(identifier):
    return alert_clusters_get(
        iris_current_user,
        session.get('permissions') or 0,
        identifier,
        fallback_customer_access=ac_current_user_has_customer_access,
    )


@alert_clusters_investigation_progress_blueprint.get('/<int:identifier>/investigation-progress')
@ac_api_requires(Permissions.alert_clusters_read)
def list_progress(identifier):
    try:
        cluster = _load_cluster(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    rows = alert_cluster_progress_list(cluster)
    flow = cluster.investigation_flow
    return response_api_success({
        'flow_id': flow.flow_id if flow else None,
        'flow_name': flow.flow_name if flow else None,
        'steps': [
            {
                'step_id': s.step_id,
                'step_order': s.step_order,
                'step_title': s.step_title,
                'step_description': s.step_description,
                'step_is_required': s.step_is_required,
            }
            for s in (flow.steps if flow else [])
        ],
        'progress': [_schema.dump(r) for r in rows],
    })


@alert_clusters_investigation_progress_blueprint.post('/<int:identifier>/investigation-progress/<int:step_id>')
@ac_api_requires(Permissions.alert_clusters_write)
def record_progress(identifier, step_id):
    try:
        cluster = _load_cluster(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    payload = request.get_json() or {}
    try:
        row = alert_cluster_progress_record(
            cluster, step_id, iris_current_user.id, note=payload.get('note')
        )
    except BusinessProcessingError as exc:
        return response_api_error(exc.get_message(), data=exc.get_data())
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_schema.dump(row))


@alert_clusters_investigation_progress_blueprint.delete('/<int:identifier>/investigation-progress/<int:step_id>')
@ac_api_requires(Permissions.alert_clusters_write)
def uncheck_progress(identifier, step_id):
    try:
        cluster = _load_cluster(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    alert_cluster_progress_uncheck(cluster, step_id)
    return response_api_deleted()
