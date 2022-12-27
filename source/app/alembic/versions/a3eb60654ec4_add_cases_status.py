"""Add cases status

Revision ID: a3eb60654ec4
Revises: 3204e9116233
Create Date: 2022-11-10 07:52:22.502834

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Integer
from sqlalchemy import text

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = 'a3eb60654ec4'
down_revision = '3204e9116233'
branch_labels = None
depends_on = None


def upgrade():

    if not _table_has_column('cases', 'status_id'):
        op.add_column('cases',
                      sa.Column('status_id', Integer, server_default=text("0"),
                                nullable=False)
                      )

    pass


def downgrade():
    pass
