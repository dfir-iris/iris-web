"""Migrate notes directories

Revision ID: c29ef01617f5
Revises: e0df2de997cc
Create Date: 2023-12-30 17:24:36.430292

"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = 'c29ef01617f5'
down_revision = 'e0df2de997cc'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('notes', 'directory_id'):

        op.execute("""
            INSERT INTO note_directory (id, name, parent_id, case_id)
            SELECT group_id, group_title, NULL, group_case_id
            FROM notes_group
        """)

        op.add_column('notes', sa.Column('directory_id', sa.BigInteger, sa.ForeignKey('note_directory.id')))

        op.execute("""
             UPDATE notes
             SET directory_id = (
                 SELECT group_id
                 FROM notes_group_link
                 WHERE notes_group_link.note_id = notes.note_id
             )
         """)


def downgrade():
    pass
