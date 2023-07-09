"""resolution status in alerts

Revision ID: e33dd011fb87
Revises: 00b43bc4e8ac
Create Date: 2023-07-03 13:28:08.882759

"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = 'e33dd011fb87'
down_revision = '00b43bc4e8ac'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('alerts', 'alert_resolution_status_id'):
        op.add_column('alerts', sa.Column('alert_resolution_status_id', sa.Integer(), nullable=True))
        op.create_foreign_key(None, 'alerts', 'alert_resolution_status',
                              ['alert_resolution_status_id'], ['resolution_status_id'])

    pass


def downgrade():
    pass
