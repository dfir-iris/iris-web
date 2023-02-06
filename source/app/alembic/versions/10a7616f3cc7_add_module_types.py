"""Add module types

Revision ID: 10a7616f3cc7
Revises: 874ba5e5da44
Create Date: 2022-02-04 07:46:32.382640

"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.

revision = '10a7616f3cc7'
down_revision = '874ba5e5da44'
branch_labels = None
depends_on = None


def upgrade():
    # Issue changes on existing user activities table and migrate existing rows
    # Add column is_from_api to user_activities if not existing and set existing ones to false
    if not _table_has_column('iris_module', 'module_type'):
        op.add_column('iris_module',
                      sa.Column('module_type', sa.Text)
                      )

        t_ua = sa.Table(
            'iris_module',
            sa.MetaData(),
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('module_type', sa.Text)
        )
        conn = op.get_bind()
        conn.execute(t_ua.update().values(
            module_type='pipeline'
        ))

    pass


def downgrade():
    pass

