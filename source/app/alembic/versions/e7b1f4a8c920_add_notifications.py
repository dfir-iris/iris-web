"""Add notification + notification_setting tables.

`notification` holds materialised per-user events (title/body/link
rendered at fire time so they survive deletion of the source object).

`notification_setting` implements the two-tier config: rows with
`user_id IS NULL` are the org-wide admin default, per-user rows
override. A partial unique index enforces at most one admin row per
(event_type, channel) since Postgres treats NULLs as distinct in the
plain uniqueness constraint on (user_id, event_type, channel).

Idempotent via `_has_table` / `index_exists`.

Revision ID: e7b1f4a8c920
Revises: d8e3f1a90c17
Create Date: 2026-07-02 09:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _has_table
from app.alembic.alembic_utils import index_exists


revision = 'e7b1f4a8c920'
down_revision = 'd8e3f1a90c17'
branch_labels = None
depends_on = None


def upgrade():
    if not _has_table('notification'):
        op.create_table(
            'notification',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.BigInteger(), nullable=False),
            sa.Column('event_type', sa.String(length=64), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('body', sa.Text(), nullable=True),
            sa.Column('link', sa.String(length=1024), nullable=True),
            sa.Column('source_type', sa.String(length=64), nullable=True),
            sa.Column('source_id', sa.BigInteger(), nullable=True),
            sa.Column('read_at', sa.DateTime(), nullable=True),
            sa.Column('emailed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('now()')),
            sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )

    if not index_exists('notification', 'ix_notification_user_id'):
        op.create_index('ix_notification_user_id', 'notification', ['user_id'])
    if not index_exists('notification', 'ix_notification_user_unread'):
        op.create_index('ix_notification_user_unread', 'notification',
                        ['user_id', 'read_at', 'created_at'])

    if not _has_table('notification_setting'):
        op.create_table(
            'notification_setting',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.BigInteger(), nullable=True),
            sa.Column('event_type', sa.String(length=64), nullable=False),
            sa.Column('channel', sa.String(length=16), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False,
                      server_default=sa.text('true')),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'event_type', 'channel',
                                name='uq_notification_setting_scope'),
        )

    # Partial unique index so at most ONE admin default row exists per
    # (event_type, channel). Postgres's plain uniqueness treats NULL
    # user_ids as distinct, which would otherwise let duplicates slip in
    # via concurrent inserts. The `WHERE user_id IS NULL` clause is what
    # makes this a single-tier constraint.
    if not index_exists('notification_setting',
                        'uq_notification_setting_admin_default'):
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "uq_notification_setting_admin_default "
            "ON notification_setting (event_type, channel) "
            "WHERE user_id IS NULL"
        )


def downgrade():
    if index_exists('notification_setting',
                    'uq_notification_setting_admin_default'):
        op.execute(
            "DROP INDEX IF EXISTS uq_notification_setting_admin_default"
        )
    if _has_table('notification_setting'):
        op.drop_table('notification_setting')

    if index_exists('notification', 'ix_notification_user_unread'):
        op.drop_index('ix_notification_user_unread', table_name='notification')
    if index_exists('notification', 'ix_notification_user_id'):
        op.drop_index('ix_notification_user_id', table_name='notification')
    if _has_table('notification'):
        op.drop_table('notification')
