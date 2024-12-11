"""Add external ref to alerts

Revision ID: 79ffcc7ef49e
Revises: 3715d4fac4de
Create Date: 2024-12-11 09:38:22.382907

"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = '79ffcc7ef49e'
down_revision = '3715d4fac4de'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('COMMIT')

    if not _table_has_column('alerts', 'external_ref_id'):
        op.add_column('alerts', sa.Column('external_ref_id', sa.Text, nullable=True))

    if not _table_has_column('alerts', 'external_ref_link'):
        op.add_column('alerts', sa.Column('external_ref_link', sa.Text, nullable=True))

    if not _table_has_column('alerts', 'external_ref_content'):
        op.add_column('alerts', sa.Column('external_ref_content', sa.JSON, nullable=True))

    return


def downgrade():
    pass
