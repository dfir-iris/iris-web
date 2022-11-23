"""Add activity no display field

Revision ID: a929ef458490
Revises: 1df4adfa3160
Create Date: 2022-11-21 15:26:49.088050

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from app.alembic.alembic_utils import _table_has_column

revision = 'a929ef458490'
down_revision = '1df4adfa3160'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('user_activity', 'display_in_ui'):
        op.add_column('user_activity',
                      sa.Column('display_in_ui', sa.Boolean, default=True)
                      )

        t_ua = sa.Table(
            'user_activity',
            sa.MetaData(),
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('display_in_ui', sa.Boolean)
        )
        conn = op.get_bind()
        conn.execute(t_ua.update().values(
            display_in_ui=True
        ))

    pass


def downgrade():
    pass
