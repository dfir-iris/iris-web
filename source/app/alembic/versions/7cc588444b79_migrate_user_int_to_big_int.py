"""Migrate user int to big int

Revision ID: 7cc588444b79
Revises: 92ecbf0f6d10
Create Date: 2022-06-14 08:28:59.027411

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '7cc588444b79'
down_revision = '92ecbf0f6d10'
branch_labels = None
depends_on = None


def upgrade():

    op.alter_column('user', 'id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)
    return


def downgrade():
    pass
