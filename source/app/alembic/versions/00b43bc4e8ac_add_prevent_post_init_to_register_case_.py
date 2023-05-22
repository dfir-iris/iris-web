"""Add prevent post-init to register case objects again during boot

Revision ID: 00b43bc4e8ac
Revises: 2604f6962838
Create Date: 2023-05-05 18:43:07.236041

"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = '00b43bc4e8ac'
down_revision = '2604f6962838'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('server_settings', 'prevent_post_objects_repush'):
        op.add_column('server_settings',
                      sa.Column('prevent_post_objects_repush', sa.Boolean(), default=False)
                      )
    pass


def downgrade():
    if _table_has_column('server_settings', 'prevent_post_objects_repush'):
        op.drop_column('server_settings', 'prevent_post_objects_repush')
    pass
