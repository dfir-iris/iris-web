"""Add war_room_id to user_activity.

The UserActivity audit trail was scoped only to cases, so anything that
happens on a war room (create, member changes, tasks, notes, sitreps,
timelines, datastore, access) had no home in the Activities tab. Adding
a nullable FK to war_room lets the tracker log war-room-scoped events
without inventing a separate table, and lets the listing endpoint
filter by war room.

Idempotent via `_has_table` / `_table_has_column` — safe to re-run.

Revision ID: d1e2f3a4b5c6
Revises: c8f3a2d47b19
Create Date: 2026-07-03 12:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _has_table, _table_has_column


revision = 'd1e2f3a4b5c6'
down_revision = 'c8f3a2d47b19'
branch_labels = None
depends_on = None


def upgrade():
    if not _has_table('user_activity'):
        return

    if not _table_has_column('user_activity', 'war_room_id'):
        op.add_column(
            'user_activity',
            sa.Column(
                'war_room_id', sa.BigInteger(),
                sa.ForeignKey('war_room.war_room_id'),
                nullable=True,
            ),
        )
        op.create_index(
            'ix_user_activity_war_room_id',
            'user_activity',
            ['war_room_id'],
        )


def downgrade():
    if not _has_table('user_activity'):
        return
    if _table_has_column('user_activity', 'war_room_id'):
        try:
            op.drop_index('ix_user_activity_war_room_id', table_name='user_activity')
        except Exception:
            pass
        op.drop_column('user_activity', 'war_room_id')
