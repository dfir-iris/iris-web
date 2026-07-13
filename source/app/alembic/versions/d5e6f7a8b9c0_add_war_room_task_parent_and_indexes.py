"""Add parent_task_id + search indexes on war_room_task.

Subtasks are single-level: a war-room task may point at another
war-room task in the same room via `parent_task_id`. Enforcement of
the "no grand-children" rule lives in the business layer (a task
that is itself a child cannot be given children) so the DB stays
simple. `ON DELETE CASCADE` on the FK: removing a parent removes its
subtasks, matching the UX expectation ("delete a task, delete its
subtasks").

Also adds three helper indexes used by the new search/filter list:
- `parent_task_id` for expand-children lookups
- `status_id` for status-filter scans
- `war_room_id, parent_task_id` composite to cheaply pull the
  top-level tree on the tasks page (parent_task_id IS NULL).

Idempotent via `_has_table` / `_table_has_column` so re-running on
environments that already applied the migration is a no-op.

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a9b0
Create Date: 2026-07-13 10:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _has_table, _table_has_column


revision = 'd5e6f7a8b9c0'
down_revision = 'c3d4e5f6a9b0'
branch_labels = None
depends_on = None


def upgrade():
    if not _has_table('war_room_task'):
        return

    if not _table_has_column('war_room_task', 'parent_task_id'):
        op.add_column(
            'war_room_task',
            sa.Column(
                'parent_task_id', sa.BigInteger(),
                sa.ForeignKey('war_room_task.task_id', ondelete='CASCADE'),
                nullable=True,
            ),
        )
        op.create_index(
            'ix_war_room_task_parent_task_id',
            'war_room_task',
            ['parent_task_id'],
        )

    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_war_room_task_status_id '
        'ON war_room_task (status_id)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_war_room_task_war_room_parent '
        'ON war_room_task (war_room_id, parent_task_id)'
    )


def downgrade():
    if not _has_table('war_room_task'):
        return

    op.execute('DROP INDEX IF EXISTS ix_war_room_task_war_room_parent')
    op.execute('DROP INDEX IF EXISTS ix_war_room_task_status_id')

    if _table_has_column('war_room_task', 'parent_task_id'):
        op.execute('DROP INDEX IF EXISTS ix_war_room_task_parent_task_id')
        op.drop_column('war_room_task', 'parent_task_id')
