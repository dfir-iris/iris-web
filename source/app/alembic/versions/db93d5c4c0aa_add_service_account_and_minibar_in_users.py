"""Add service account and minibar in users

Revision ID: db93d5c4c0aa
Revises: 2a4a8330b908
Create Date: 2023-04-26 14:14:47.990230

"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = 'db93d5c4c0aa'
down_revision = '2a4a8330b908'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('user', 'is_service_account'):
        op.add_column('user',
                      sa.Column('is_service_account', sa.Boolean, default=False))

    if not _table_has_column('user', 'has_mini_sidebar'):
        op.add_column('user',
                      sa.Column('has_mini_sidebar', sa.Boolean, default=False))

    pass


def downgrade():
    if _table_has_column('user', 'is_service_account'):
        op.drop_column('user', 'is_service_account')

    if _table_has_column('user', 'has_mini_sidebar'):
        op.drop_column('user', 'has_mini_sidebar')

    pass
