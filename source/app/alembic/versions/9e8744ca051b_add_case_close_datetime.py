"""Add case close_datetime

Revision ID: 9e8744ca051b
Revises: 11aa5b725b8e
Create Date: 2024-11-18 16:03:05.620518

"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column


# revision identifiers, used by Alembic.
revision = '9e8744ca051b'
down_revision = 'd5a720d1b99b'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('COMMIT')
    
    if not _table_has_column('cases', 'close_datetime'):
        op.add_column('cases',
                      sa.Column('close_datetime', sa.DateTime, default=False),
                      # insert_after requires alembic 1.10.0 or higher
                      #insert_after = 'initial_date'
                      )
    return


def downgrade():
    if _table_has_column('cases', 'close_datetime'):
        op.drop_column('cases', 'close_datetime')
    return
