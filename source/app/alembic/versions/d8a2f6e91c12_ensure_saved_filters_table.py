"""Ensure the saved_filters table exists.

`SavedFilter` is referenced by both the alerts saved-filters endpoints
(historical) and the new cases saved-filters endpoints, but the table
was previously only created by `db.create_all()` at first boot. Long-
lived deployments that never ran `create_all` against an empty database
(or skipped it after a partial restore) end up without the table, and
the very first POST against `/api/v2/alerts-filters` or
`/api/v2/cases-filters` then 500s with `relation "saved_filters" does
not exist`.

This migration creates the table idempotently — `_has_table` short-
circuits the create when the table already exists, so deployments
where `db.create_all()` already provisioned it just get a no-op
upgrade.

Revision ID: d8a2f6e91c12
Revises: c7f1e2a4d810
Create Date: 2026-06-26 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _has_table


revision = 'd8a2f6e91c12'
down_revision = 'c7f1e2a4d810'
branch_labels = None
depends_on = None


def upgrade():
    if _has_table('saved_filters'):
        return

    op.create_table(
        'saved_filters',
        sa.Column('filter_id', sa.BigInteger(), primary_key=True),
        sa.Column('created_by', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=False),
        sa.Column('filter_name', sa.Text(), nullable=False),
        sa.Column('filter_description', sa.Text(), nullable=True),
        sa.Column('filter_data', sa.JSON(), nullable=False),
        sa.Column('filter_is_private', sa.Boolean(), nullable=False),
        sa.Column('filter_type', sa.Text(), nullable=False),
    )


def downgrade():
    # Intentional no-op: dropping the table would lose every saved
    # filter the user has built up. The table also predates this
    # migration (it was created by `db.create_all()` on fresh
    # installs), so dropping it on downgrade would punish anyone who
    # was already using the alerts saved-filters feature.
    return
