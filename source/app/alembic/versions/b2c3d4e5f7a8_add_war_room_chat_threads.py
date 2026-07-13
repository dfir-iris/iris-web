"""Add threading to war_room_chat_message + follower table.

Threads are two-level: a top-level message can have any number of
replies pointing at it via `parent_message_id`, but replies cannot
themselves be parents (enforced at the business layer). A thread root
that has been promoted to a named topic via `/thread <title>` carries
its label in `thread_title`.

`war_room_thread_follower` is the per-user follow flag for a thread
root — used by the UI today and the notification pipeline later.

Idempotent via `_has_table` / `_table_has_column` so re-running on
environments that already applied the migration is a no-op.

Revision ID: b2c3d4e5f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-28 15:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _has_table, _table_has_column


revision = 'b2c3d4e5f7a8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    if _has_table('war_room_chat_message'):
        if not _table_has_column('war_room_chat_message', 'parent_message_id'):
            op.add_column(
                'war_room_chat_message',
                sa.Column(
                    'parent_message_id', sa.BigInteger(),
                    sa.ForeignKey(
                        'war_room_chat_message.message_id', ondelete='CASCADE'
                    ),
                    nullable=True,
                ),
            )
            op.create_index(
                'ix_war_room_chat_message_parent_message_id',
                'war_room_chat_message',
                ['parent_message_id'],
            )
        if not _table_has_column('war_room_chat_message', 'thread_title'):
            op.add_column(
                'war_room_chat_message',
                sa.Column('thread_title', sa.String(length=160), nullable=True),
            )

    if not _has_table('war_room_thread_follower'):
        op.create_table(
            'war_room_thread_follower',
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column(
                'message_id', sa.BigInteger(),
                sa.ForeignKey(
                    'war_room_chat_message.message_id', ondelete='CASCADE'
                ),
                nullable=False,
            ),
            sa.Column(
                'user_id', sa.BigInteger(),
                sa.ForeignKey('user.id', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column(
                'created_at', sa.DateTime(), nullable=False,
                server_default=sa.text('now()'),
            ),
            sa.UniqueConstraint('message_id', 'user_id',
                                name='uq_war_room_thread_follower'),
        )
        op.create_index(
            'ix_war_room_thread_follower_message_id',
            'war_room_thread_follower',
            ['message_id'],
        )
        op.create_index(
            'ix_war_room_thread_follower_user_id',
            'war_room_thread_follower',
            ['user_id'],
        )


def downgrade():
    if _has_table('war_room_thread_follower'):
        op.drop_index(
            'ix_war_room_thread_follower_user_id',
            table_name='war_room_thread_follower',
        )
        op.drop_index(
            'ix_war_room_thread_follower_message_id',
            table_name='war_room_thread_follower',
        )
        op.drop_table('war_room_thread_follower')

    if _has_table('war_room_chat_message'):
        if _table_has_column('war_room_chat_message', 'thread_title'):
            op.drop_column('war_room_chat_message', 'thread_title')
        if _table_has_column('war_room_chat_message', 'parent_message_id'):
            op.drop_index(
                'ix_war_room_chat_message_parent_message_id',
                table_name='war_room_chat_message',
            )
            op.drop_column('war_room_chat_message', 'parent_message_id')
