"""Case templates note groups to directories

Revision ID: 35c095f8be2b
Revises: 20a9c0fd56e1
Create Date: 2024-01-15 13:53:48.946919

"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = '35c095f8be2b'
down_revision = '20a9c0fd56e1'
branch_labels = None
depends_on = None


def upgrade():
    # Change ``notes_group`` field to ``note_directory`` in Case Templates table
    if _table_has_column('case_template', 'note_groups'):
        op.alter_column('case_template', 'note_groups', new_column_name='note_directories')

    pass


def downgrade():
    pass
