"""Add `category` column to war_room_timeline_event.

War-room timelines now expose a free-form category badge on events,
mirroring the case timeline's `event_category` taxonomy — but kept as
a plain string rather than a FK so war rooms don't need to share the
global category table.

Idempotent via `_table_has_column` so re-running on an environment
that already has the column is a no-op.

Revision ID: a1b2c3d4e5f6
Revises: f6c213d80b41
Create Date: 2026-06-28 12:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _has_table, _table_has_column


revision = 'a1b2c3d4e5f6'
down_revision = 'f6c213d80b41'
branch_labels = None
depends_on = None


def upgrade():
    if not _has_table('war_room_timeline_event'):
        return
    if _table_has_column('war_room_timeline_event', 'category'):
        return
    op.add_column(
        'war_room_timeline_event',
        sa.Column('category', sa.String(length=64), nullable=True),
    )


def downgrade():
    if not _has_table('war_room_timeline_event'):
        return
    if not _table_has_column('war_room_timeline_event', 'category'):
        return
    op.drop_column('war_room_timeline_event', 'category')
