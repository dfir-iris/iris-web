"""Add modification history to case objects

Revision ID: 9e4947a207a6
Revises: 35c095f8be2b
Create Date: 2024-02-16 15:22:17.780516

"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = '9e4947a207a6'
down_revision = '35c095f8be2b'
branch_labels = None
depends_on = None


def upgrade():
    tables = ['ioc', 'case_assets', 'case_received_file', 'case_tasks', 'notes', 'cases_events']
    for table in tables:
        if not _table_has_column(table, 'modification_history'):
            try:
                op.add_column(table,
                              sa.Column('modification_history', sa.JSON)
                              )
                t_ua = sa.Table(
                    table,
                    sa.MetaData(),
                    sa.Column('modification_history', sa.JSON)
                )
                conn = op.get_bind()
                conn.execute(t_ua.update().values(
                    modification_history={}
                ))

                # Commit the transaction
                conn.commit()

            except Exception as e:
                print(f"Error adding column to {table}: {e}")
                continue
    pass


def downgrade():
    pass
