#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Business layer for the war-room graph board.

The graph board is a free-form 2D canvas where every attached case is
a node and the operator can drop annotations and draw edges with
labels. The schema is intentionally tiny — `kind`, `ref_id`, position,
label, note — and we ship the entire graph in one `GET` and replace
it with one `PUT` so we don't have to worry about partial-update
conflict resolution during a crisis.
"""

from app.db import db
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.war_rooms import WarRoomCase
from app.models.war_rooms import WarRoomGraphEdge
from app.models.war_rooms import WarRoomGraphNode


_VALID_KINDS = {'case', 'annotation', 'group'}


def list_graph(war_room_id):
    nodes = (
        WarRoomGraphNode.query
        .filter(WarRoomGraphNode.war_room_id == war_room_id)
        .all()
    )
    edges = (
        WarRoomGraphEdge.query
        .filter(WarRoomGraphEdge.war_room_id == war_room_id)
        .all()
    )
    return nodes, edges


def replace_graph(war_room_id, nodes, edges):
    """Drop & re-insert the graph in a single transaction.

    Nodes that reference cases are auto-derived from the war-room's
    case attachments if `kind=case` but no `ref_id` is given — keeps
    the SPA from having to do a separate join just to get a node id.
    """
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise BusinessProcessingError('nodes and edges must be lists')

    # Wipe out the old layout in one go. The DB layer cascades from
    # nodes -> edges so we delete edges first.
    WarRoomGraphEdge.query.filter(
        WarRoomGraphEdge.war_room_id == war_room_id
    ).delete()
    WarRoomGraphNode.query.filter(
        WarRoomGraphNode.war_room_id == war_room_id
    ).delete()
    db.session.flush()

    # Map client-side temp ids onto the new persisted ids so the edge
    # list can reference nodes that were just created.
    id_map = {}
    for n in nodes:
        kind = n.get('kind')
        if kind not in _VALID_KINDS:
            raise BusinessProcessingError(f'Invalid node kind: {kind}')
        row = WarRoomGraphNode()
        row.war_room_id = war_room_id
        row.kind = kind
        row.ref_id = n.get('ref_id')
        row.label = (n.get('label') or '')[:1024]
        row.note_md = n.get('note_md')
        row.color = n.get('color')
        row.x = float(n.get('x', 0))
        row.y = float(n.get('y', 0))
        db.session.add(row)
        db.session.flush()
        if 'tmp_id' in n:
            id_map[n['tmp_id']] = row.node_id
        if 'node_id' in n:
            id_map[n['node_id']] = row.node_id

    for e in edges:
        from_id = e.get('from_node_id')
        to_id = e.get('to_node_id')
        # Allow the caller to use either persisted ids it had before the
        # swap, or `tmp_id` values it just allocated client-side.
        from_id = id_map.get(from_id, from_id)
        to_id = id_map.get(to_id, to_id)
        if from_id is None or to_id is None:
            continue
        row = WarRoomGraphEdge()
        row.war_room_id = war_room_id
        row.from_node_id = from_id
        row.to_node_id = to_id
        row.label = (e.get('label') or '')[:512] or None
        row.note_md = e.get('note_md')
        row.style = e.get('style')
        db.session.add(row)

    db.session.commit()


def auto_seed_case_nodes(war_room_id):
    """Place a node for every attached case that's not already on the
    graph. Called the first time the operator opens the graph tab so
    they don't see an empty canvas with cases hidden somewhere.
    """
    existing = (
        WarRoomGraphNode.query
        .with_entities(WarRoomGraphNode.ref_id)
        .filter(WarRoomGraphNode.war_room_id == war_room_id,
                WarRoomGraphNode.kind == 'case')
        .all()
    )
    have = {row.ref_id for row in existing}

    cases = (
        WarRoomCase.query
        .with_entities(WarRoomCase.case_id)
        .filter(WarRoomCase.war_room_id == war_room_id)
        .all()
    )
    missing = [c.case_id for c in cases if c.case_id not in have]
    if not missing:
        return

    # Place new nodes on a grid so they don't overlap.
    cols = 4
    for idx, case_id in enumerate(missing):
        row = WarRoomGraphNode()
        row.war_room_id = war_room_id
        row.kind = 'case'
        row.ref_id = case_id
        row.label = f'Case #{case_id}'
        row.x = float((idx % cols) * 220)
        row.y = float((idx // cols) * 160)
        db.session.add(row)

    db.session.commit()
