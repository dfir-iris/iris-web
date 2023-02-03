"""Add created by in events

Revision ID: ca93d4b54571
Revises: 79a9a54e8f9d
Create Date: 2022-05-08 14:58:38.839651

"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.

revision = 'ca93d4b54571'
down_revision = '79a9a54e8f9d'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('cases_events', 'modification_history'):
        op.add_column('cases_events',
                      sa.Column('modification_history', sa.JSON)
                      )
    pass


def downgrade():
    pass
