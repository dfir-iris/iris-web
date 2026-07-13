"""Add archive columns to war_room.

Archive is a filing decision independent from the operational state
(`open` / `active` / `standby` / `closed`). A war room can be archived
regardless of its state — the point is to move it out of the default
sight line once the operator no longer needs to see it, while keeping
it fully readable.

Two nullable columns are added:

  * `archived_at`     — timestamp; NULL when the room is live.
  * `archived_by_id`  — FK to `user.id`; who filed the room away.

Idempotent via `_has_table` / `_table_has_column` so re-running is a
no-op.

Revision ID: c4d1a2b7f503
Revises: b2c3d4e5f7a8
Create Date: 2026-07-01 12:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _has_table, _table_has_column


revision = 'c4d1a2b7f503'
down_revision = 'b2c3d4e5f7a8'
branch_labels = None
depends_on = None


def upgrade():
    if not _has_table('war_room'):
        return

    if not _table_has_column('war_room', 'archived_at'):
        op.add_column(
            'war_room',
            sa.Column('archived_at', sa.DateTime(), nullable=True),
        )
        op.create_index(
            'ix_war_room_archived_at',
            'war_room',
            ['archived_at'],
        )

    if not _table_has_column('war_room', 'archived_by_id'):
        op.add_column(
            'war_room',
            sa.Column(
                'archived_by_id', sa.BigInteger(),
                sa.ForeignKey('user.id'),
                nullable=True,
            ),
        )


def downgrade():
    if not _has_table('war_room'):
        return
    if _table_has_column('war_room', 'archived_by_id'):
        op.drop_column('war_room', 'archived_by_id')
    if _table_has_column('war_room', 'archived_at'):
        try:
            op.drop_index('ix_war_room_archived_at', table_name='war_room')
        except Exception:
            pass
        op.drop_column('war_room', 'archived_at')
