"""Add namespace to tags

Revision ID: e0df2de997cc
Revises: d207b4d13385
Create Date: 2023-12-30 09:24:32.991449

"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = 'e0df2de997cc'
down_revision = 'd207b4d13385'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('tags', 'tag_namespace'):
        # Add namespace if it doesn't exist
        op.add_column('tags', sa.Column('tag_namespace', sa.Text(), nullable=True))
    pass


def downgrade():
    pass
