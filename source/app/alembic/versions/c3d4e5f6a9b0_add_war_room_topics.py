"""Add war_room_topic table + topic_id column on war_room_chat_message.

Topics are top-level partitions of the chat stream — each war room
has one non-archivable "Main" topic (created lazily by the business
layer on first read) plus any number of operator-created ones. A
message with `topic_id IS NULL` is on Main; the read path treats
NULL and the Main topic row as equivalent so pre-migration rows keep
working without a backfill.

Archive is soft (`archived_at`). No hard delete — archived topics
still render (read-only) in the sidebar.

Idempotent via `_has_table` / `_table_has_column` so re-running on
environments that already applied the migration is a no-op.

Revision ID: c3d4e5f6a9b0
Revises: f3c8d2a1b47e
Create Date: 2026-07-09 10:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _has_table, _table_has_column


revision = 'c3d4e5f6a9b0'
down_revision = 'f3c8d2a1b47e'
branch_labels = None
depends_on = None


def upgrade():
    if not _has_table('war_room_topic'):
        op.create_table(
            'war_room_topic',
            sa.Column('topic_id', sa.BigInteger(), primary_key=True),
            sa.Column(
                'war_room_id', sa.BigInteger(),
                sa.ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('name', sa.String(length=80), nullable=False),
            sa.Column(
                'is_main', sa.Boolean(), nullable=False,
                server_default=sa.text('false'),
            ),
            sa.Column(
                'created_by_id', sa.BigInteger(),
                sa.ForeignKey('user.id'), nullable=True,
            ),
            sa.Column(
                'created_at', sa.DateTime(), nullable=False,
                server_default=sa.text('now()'),
            ),
            sa.Column('archived_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('war_room_id', 'name',
                                name='uq_war_room_topic_name'),
        )
        op.create_index(
            'ix_war_room_topic_war_room_id',
            'war_room_topic',
            ['war_room_id'],
        )

    if _has_table('war_room_chat_message'):
        if not _table_has_column('war_room_chat_message', 'topic_id'):
            op.add_column(
                'war_room_chat_message',
                sa.Column(
                    'topic_id', sa.BigInteger(),
                    sa.ForeignKey(
                        'war_room_topic.topic_id', ondelete='SET NULL'
                    ),
                    nullable=True,
                ),
            )
            op.create_index(
                'ix_war_room_chat_message_topic_id',
                'war_room_chat_message',
                ['topic_id'],
            )


def downgrade():
    if _has_table('war_room_chat_message'):
        if _table_has_column('war_room_chat_message', 'topic_id'):
            op.drop_index(
                'ix_war_room_chat_message_topic_id',
                table_name='war_room_chat_message',
            )
            op.drop_column('war_room_chat_message', 'topic_id')

    if _has_table('war_room_topic'):
        op.drop_index(
            'ix_war_room_topic_war_room_id',
            table_name='war_room_topic',
        )
        op.drop_table('war_room_topic')
