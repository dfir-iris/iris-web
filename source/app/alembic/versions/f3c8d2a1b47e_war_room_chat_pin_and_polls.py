"""War-room chat: pin toggle + polls schema.

Adds analyst affordances on the war-room chat stream:

  * `war_room_chat_message.is_pinned` — sticky flag surfaced in the
    "Decisions & Pins" sidebar alongside the existing `kind='pin'`
    system rows.
  * `war_room_chat_poll` — a poll posted inline in the stream (via a
    companion `WarRoomChatMessage` with `kind='poll'`).
  * `war_room_chat_poll_option` — the selectable answers for a poll.
  * `war_room_chat_poll_vote` — each user's vote per option; composite
    PK `(option_id, user_id)` idempotent-by-construction.

Every step is guarded by `_has_table` / `_table_has_column` so the
migration is idempotent — safe to re-run on partially-upgraded
environments.

Revision ID: f3c8d2a1b47e
Revises: e5b2a41c9d7e
Create Date: 2026-07-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _has_table
from app.alembic.alembic_utils import _table_has_column


revision = 'f3c8d2a1b47e'
down_revision = 'e5b2a41c9d7e'
branch_labels = None
depends_on = None


def _add_is_pinned_column():
    if _table_has_column('war_room_chat_message', 'is_pinned'):
        return
    op.add_column(
        'war_room_chat_message',
        sa.Column('is_pinned', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')),
    )


def _create_war_room_chat_poll():
    if _has_table('war_room_chat_poll'):
        return
    op.create_table(
        'war_room_chat_poll',
        sa.Column('poll_id', sa.BigInteger(), primary_key=True),
        sa.Column('war_room_id', sa.BigInteger(),
                  sa.ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('author_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('is_multi_select', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')),
        sa.Column('is_anonymous', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')),
        sa.Column('closes_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('chat_message_id', sa.BigInteger(),
                  sa.ForeignKey('war_room_chat_message.message_id',
                                ondelete='SET NULL'),
                  nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
    )


def _create_war_room_chat_poll_option():
    if _has_table('war_room_chat_poll_option'):
        return
    op.create_table(
        'war_room_chat_poll_option',
        sa.Column('option_id', sa.BigInteger(), primary_key=True),
        sa.Column('poll_id', sa.BigInteger(),
                  sa.ForeignKey('war_room_chat_poll.poll_id',
                                ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('label', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False,
                  server_default=sa.text('0')),
    )


def _create_war_room_chat_poll_vote():
    if _has_table('war_room_chat_poll_vote'):
        return
    op.create_table(
        'war_room_chat_poll_vote',
        sa.Column('option_id', sa.BigInteger(),
                  sa.ForeignKey('war_room_chat_poll_option.option_id',
                                ondelete='CASCADE'),
                  primary_key=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(),
                  sa.ForeignKey('user.id', ondelete='CASCADE'),
                  primary_key=True, nullable=False),
        sa.Column('voted_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
    )


def upgrade():
    _add_is_pinned_column()
    _create_war_room_chat_poll()
    _create_war_room_chat_poll_option()
    _create_war_room_chat_poll_vote()


def downgrade():
    op.drop_table('war_room_chat_poll_vote')
    op.drop_table('war_room_chat_poll_option')
    op.drop_table('war_room_chat_poll')
    if _table_has_column('war_room_chat_message', 'is_pinned'):
        op.drop_column('war_room_chat_message', 'is_pinned')
