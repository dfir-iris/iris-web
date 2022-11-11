"""Add customer extended fields

Revision ID: 1df4adfa3160
Revises: a3eb60654ec4
Create Date: 2022-11-11 19:23:30.355618

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from app.alembic.alembic_utils import _table_has_column

revision = '1df4adfa3160'
down_revision = 'a3eb60654ec4'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('client', 'description'):
        op.add_column('client',
                      sa.Column('description', sa.Text())
                      )

    if not _table_has_column('client', 'sla'):
        op.add_column('client',
                      sa.Column('sla', sa.Text())
                      )

    if not _table_has_column('client', 'creation_date'):
        op.add_column('client',
                      sa.Column('creation_date', sa.DateTime())
                      )

    if not _table_has_column('client', 'last_update_date'):
        op.add_column('client',
                      sa.Column('last_update_date', sa.DateTime())
                      )

    if not _table_has_column('client', 'created_by'):
        op.add_column('client',
                      sa.Column('created_by',  sa.BigInteger(), sa.ForeignKey('user.id'), nullable=True)
                      )

    pass


def downgrade():
    pass
