"""Add dark mode

Revision ID: b664ca1203a4
Revises: 2df770a4989c
Create Date: 2022-03-06 18:00:46.251407

"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.

revision = 'b664ca1203a4'
down_revision = '2df770a4989c'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('user', 'in_dark_mode'):
        op.add_column('user',
                      sa.Column('in_dark_mode', sa.Boolean)
                      )

        t_ua = sa.Table(
            'user',
            sa.MetaData(),
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('in_dark_mode', sa.Boolean)
        )
        conn = op.get_bind()
        conn.execute(t_ua.update().values(
            in_dark_mode=False
        ))

    pass


def downgrade():
    pass
