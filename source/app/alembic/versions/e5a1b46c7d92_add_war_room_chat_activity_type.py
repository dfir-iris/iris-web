"""Add `activity_type` column to `war_room_chat_message`.

A finer-grained classifier for case-activity rows on the war-room
stream. Where the existing `kind` column already says "this is a case
activity, this is a task assignment, this is a SitRep publish", the
new `activity_type` says *what kind* of case activity it is — note
created vs. IOC updated vs. asset deleted, etc. — so the stream's
filter pane can offer per-case, per-type checkboxes without
re-parsing the activity description on the client.

Nullable: most existing rows (operator messages, sytem rows that
predate this migration) carry no type. The ingest hook starts
stamping new rows on the next request after the migration applies.

Idempotent — guarded by `_table_has_column` so re-running on an
already-upgraded environment is a no-op.

Revision ID: e5a1b46c7d92
Revises: d4f0a23c8e51
Create Date: 2026-06-27 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _has_table
from app.alembic.alembic_utils import _table_has_column
from app.alembic.alembic_utils import index_exists


revision = 'e5a1b46c7d92'
down_revision = 'd4f0a23c8e51'
branch_labels = None
depends_on = None


def upgrade():
    if not _has_table('war_room_chat_message'):
        # The base war-room migration must run first; bail quietly if
        # the parent table is somehow missing.
        return

    if not _table_has_column('war_room_chat_message', 'activity_type'):
        op.add_column(
            'war_room_chat_message',
            sa.Column('activity_type', sa.String(48), nullable=True),
        )

    if not index_exists(
        'war_room_chat_message', 'ix_war_room_chat_message_activity_type'
    ):
        op.create_index(
            'ix_war_room_chat_message_activity_type',
            'war_room_chat_message',
            ['activity_type'],
        )


def downgrade():
    if _has_table('war_room_chat_message'):
        if index_exists(
            'war_room_chat_message', 'ix_war_room_chat_message_activity_type'
        ):
            op.drop_index(
                'ix_war_room_chat_message_activity_type',
                table_name='war_room_chat_message',
            )
        if _table_has_column('war_room_chat_message', 'activity_type'):
            op.drop_column('war_room_chat_message', 'activity_type')
