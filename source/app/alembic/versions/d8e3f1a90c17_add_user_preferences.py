"""Add a generic per-user preferences JSONB column.

A single `user.preferences` JSONB column lets the SPA persist small
per-user settings without a new table per feature. Callers agree on
top-level keys — e.g. `war_room_stream` for the chat sidebar filter
selection — and read/write with `jsonb_set`-style updates.

Idempotent via `_has_table` / `_table_has_column`.

Revision ID: d8e3f1a90c17
Revises: c4d1a2b7f503
Create Date: 2026-07-01 12:30:00.000000
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

from app.alembic.alembic_utils import _has_table, _table_has_column


revision = 'd8e3f1a90c17'
down_revision = 'c4d1a2b7f503'
branch_labels = None
depends_on = None


def upgrade():
    if not _has_table('user'):
        return
    if not _table_has_column('user', 'preferences'):
        op.add_column(
            'user',
            sa.Column('preferences', JSONB, nullable=True),
        )


def downgrade():
    if not _has_table('user'):
        return
    if _table_has_column('user', 'preferences'):
        op.drop_column('user', 'preferences')
