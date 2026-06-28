"""Drop the war-room graph tables.

The cases-as-graph board was removed from the war-room workspace —
the operator-driven graph wasn't getting use during real incidents
and the data it stored (free-form node positions, annotation notes,
edges) was orphaned. Dropping the tables avoids leaving dead rows
hanging on every war room.

Idempotent guards via `_has_table` so re-running on environments that
already removed the tables is a no-op.

Revision ID: f6c213d80b41
Revises: e5a1b46c7d92
Create Date: 2026-06-28 09:00:00.000000
"""
from alembic import op

from app.alembic.alembic_utils import _has_table


revision = 'f6c213d80b41'
down_revision = 'e5a1b46c7d92'
branch_labels = None
depends_on = None


def upgrade():
    # Edges first — they FK into nodes.
    if _has_table('war_room_graph_edge'):
        op.drop_table('war_room_graph_edge')
    if _has_table('war_room_graph_node'):
        op.drop_table('war_room_graph_node')


def downgrade():
    # Intentionally not re-created. The feature is gone; reviving it
    # would mean re-introducing the data model from the original
    # `d4f0a23c8e51_add_war_rooms.py` migration. If the feature is
    # ever brought back, that migration's `_create_war_room_graph`
    # helper is the source of truth.
    pass
