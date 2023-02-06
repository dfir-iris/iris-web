"""Add objects attributes

Revision ID: 2df770a4989c
Revises: 10a7616f3cc7
Create Date: 2022-02-11 20:13:14.365469

"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.

revision = '2df770a4989c'
down_revision = '10a7616f3cc7'
branch_labels = None
depends_on = None


def upgrade():
    tables = ['ioc', 'case_assets', 'case_received_file', 'case_tasks', 'notes', 'cases_events', 'cases', 'client']
    for table in tables:
        if not _table_has_column(table, 'custom_attributes'):
            op.add_column(table,
                          sa.Column('custom_attributes', sa.JSON)
                          )

            t_ua = sa.Table(
                table,
                sa.MetaData(),
                sa.Column('custom_attributes', sa.JSON)
            )
            conn = op.get_bind()
            conn.execute(t_ua.update().values(
                custom_attributes={}
            ))

    pass


def downgrade():
    pass
