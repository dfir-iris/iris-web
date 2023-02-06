"""Add user external ID

Revision ID: 92ecbf0f6d10
Revises: cd519d2d24df
Create Date: 2022-06-13 08:59:04.860887

"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.

revision = '92ecbf0f6d10'
down_revision = 'cd519d2d24df'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('user', 'external_id'):
        op.add_column('user',
                      sa.Column('external_id', sa.Text)
                      )

        t_ua = sa.Table(
            'user',
            sa.MetaData(),
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('external_id', sa.Text)
        )
        conn = op.get_bind()
        conn.execute(t_ua.update().values(
            external_id=None
        ))

    pass


def downgrade():
    pass
