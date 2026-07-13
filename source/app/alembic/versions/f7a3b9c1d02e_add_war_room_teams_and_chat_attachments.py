"""Add per-war-room teams and chat message attachments.

Feature 1: `war_room_team` + `war_room_team_member` support @team
mentions in chat, threads, notes and tasks. Teams are per-war-room and
cascade with the room.

Feature 2: `war_room_chat_message.attachments` is a JSONB column that
holds inline file references (list of `{file_id, filename, mime_type,
size_bytes}`) pointing at rows in `war_room_datastore_file`.

Idempotent via `_has_table` / `_table_has_column` so re-running is safe
across environments that already applied the migration.

Revision ID: f7a3b9c1d02e
Revises: d5e6f7a8b9c0
Create Date: 2026-07-13 10:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.alembic_utils import _has_table, _table_has_column


revision = 'f7a3b9c1d02e'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    if not _has_table('war_room_team'):
        op.create_table(
            'war_room_team',
            sa.Column('team_id', sa.BigInteger(), primary_key=True),
            sa.Column(
                'war_room_id', sa.BigInteger(),
                sa.ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('name', sa.String(length=80), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('color', sa.String(length=7), nullable=True),
            sa.Column(
                'created_at', sa.DateTime(), nullable=False,
                server_default=sa.text('now()'),
            ),
            sa.Column(
                'created_by_id', sa.BigInteger(),
                sa.ForeignKey('user.id'), nullable=True,
            ),
            sa.UniqueConstraint('war_room_id', 'name',
                                name='uq_war_room_team_name'),
        )
        op.create_index(
            'ix_war_room_team_war_room_id',
            'war_room_team',
            ['war_room_id'],
        )

    if not _has_table('war_room_team_member'):
        op.create_table(
            'war_room_team_member',
            sa.Column(
                'team_id', sa.BigInteger(),
                sa.ForeignKey('war_room_team.team_id', ondelete='CASCADE'),
                primary_key=True, nullable=False,
            ),
            sa.Column(
                'user_id', sa.BigInteger(),
                sa.ForeignKey('user.id', ondelete='CASCADE'),
                primary_key=True, nullable=False,
            ),
            sa.Column(
                'added_at', sa.DateTime(), nullable=False,
                server_default=sa.text('now()'),
            ),
            sa.Column(
                'added_by_id', sa.BigInteger(),
                sa.ForeignKey('user.id'), nullable=True,
            ),
            sa.UniqueConstraint('team_id', 'user_id',
                                name='uq_war_room_team_member'),
        )

    if _has_table('war_room_chat_message') \
            and not _table_has_column('war_room_chat_message', 'attachments'):
        op.add_column(
            'war_room_chat_message',
            sa.Column('attachments', postgresql.JSONB(), nullable=True),
        )


def downgrade():
    if _has_table('war_room_chat_message') \
            and _table_has_column('war_room_chat_message', 'attachments'):
        op.drop_column('war_room_chat_message', 'attachments')

    if _has_table('war_room_team_member'):
        op.drop_table('war_room_team_member')

    if _has_table('war_room_team'):
        op.drop_index(
            'ix_war_room_team_war_room_id',
            table_name='war_room_team',
        )
        op.drop_table('war_room_team')
