"""Add objects attributes

Revision ID: 2df770a4989c
Revises: 10a7616f3cc7
Create Date: 2022-02-11 20:13:14.365469

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy import engine_from_config
from sqlalchemy.engine import reflection

revision = '2df770a4989c'
down_revision = '10a7616f3cc7'
branch_labels = None
depends_on = None


def upgrade():
    tables = ['ioc', 'case_assets', 'case_received_file', 'case_tasks', 'notes', 'cases_events', 'cases']
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


def _table_has_column(table, column):
    config = op.get_context().config
    engine = engine_from_config(
        config.get_section(config.config_ini_section), prefix='sqlalchemy.')
    insp = reflection.Inspector.from_engine(engine)
    has_column = False

    for col in insp.get_columns(table):
        if column != col['name']:
            continue
        has_column = True
    return has_column