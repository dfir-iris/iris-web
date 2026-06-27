#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""War-room graph REST routes + case summary side-sheet endpoint."""

from flask import Blueprint, request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.v2.war_rooms.access import require_war_room_read
from app.blueprints.rest.v2.war_rooms.access import require_war_room_write
from app.business.case_summary import case_summary
from app.business.cases import cases_exists
from app.business.war_room_graph import auto_seed_case_nodes
from app.business.war_room_graph import list_graph
from app.business.war_room_graph import replace_graph
from app.models.authorization import CaseAccessLevel
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


war_rooms_graph_blueprint = Blueprint(
    'war_rooms_graph_rest_v2', __name__, url_prefix='/<int:war_room_id>/graph'
)


def _serialize_node(n):
    return {
        'node_id': n.node_id,
        'kind': n.kind,
        'ref_id': n.ref_id,
        'label': n.label,
        'note_md': n.note_md,
        'color': n.color,
        'x': n.x,
        'y': n.y,
    }


def _serialize_edge(e):
    return {
        'edge_id': e.edge_id,
        'from_node_id': e.from_node_id,
        'to_node_id': e.to_node_id,
        'label': e.label,
        'note_md': e.note_md,
        'style': e.style,
    }


@war_rooms_graph_blueprint.get('')
@ac_api_requires()
def get_graph(war_room_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    # Auto-place any case nodes that haven't been positioned yet so the
    # canvas is never empty on first open.
    try:
        auto_seed_case_nodes(war_room_id)
    except Exception:
        pass
    nodes, edges = list_graph(war_room_id)
    return response_api_success({
        'nodes': [_serialize_node(n) for n in nodes],
        'edges': [_serialize_edge(e) for e in edges],
    })


@war_rooms_graph_blueprint.put('')
@ac_api_requires()
def put_graph(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        replace_graph(war_room_id, raw.get('nodes', []), raw.get('edges', []))
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    nodes, edges = list_graph(war_room_id)
    return response_api_success({
        'nodes': [_serialize_node(n) for n in nodes],
        'edges': [_serialize_edge(e) for e in edges],
    })
