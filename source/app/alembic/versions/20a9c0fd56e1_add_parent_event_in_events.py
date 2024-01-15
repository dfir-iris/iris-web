"""Add parent event in events

Revision ID: 20a9c0fd56e1
Revises: c29ef01617f5
Create Date: 2024-01-15 08:44:15.685226

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import ForeignKey

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = '20a9c0fd56e1'
down_revision = 'c29ef01617f5'
branch_labels = None
depends_on = None


def upgrade():
    # Add the parent event ID column if it does not exist
    if not _table_has_column('cases_events', 'parent_event_id'):
        op.add_column('cases_events',
                      sa.Column('parent_event_id',
                                sa.BigInteger(),
                                ForeignKey('cases_events.event_id'),
                                nullable=True))

        op.create_check_constraint('check_different_ids',
                                   'cases_events',
                                   'event_id != parent_event_id')

    pass


def downgrade():
    pass
