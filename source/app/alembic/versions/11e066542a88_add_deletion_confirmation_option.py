"""Add deletion confirmation option

Revision ID: 11e066542a88
Revises: 20447ecb2245
Create Date: 2022-09-25 08:51:13.383431

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy import Boolean

from app.alembic.alembic_utils import _table_has_column

revision = '11e066542a88'
down_revision = '20447ecb2245'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('user', 'has_deletion_confirmation'):
        op.add_column('user',
                      sa.Column('has_deletion_confirmation',  Boolean(), nullable=False, server_default='false')
                      )
    pass


def downgrade():
    pass
