"""Add event flag

Revision ID: 3204e9116233
Revises: 11e066542a88
Create Date: 2022-10-02 13:44:36.996070

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from app.alembic.alembic_utils import _table_has_column

revision = '3204e9116233'
down_revision = '11e066542a88'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('cases_events', 'event_is_flagged'):
        op.add_column('cases_events',
                      sa.Column('event_is_flagged', sa.Boolean, default=False)
                      )

    pass


def downgrade():
    pass
