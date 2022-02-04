"""Add module types

Revision ID: 10a7616f3cc7
Revises: c773a35c280f
Create Date: 2022-02-04 07:46:32.382640

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy import engine_from_config
from sqlalchemy.engine import reflection

revision = '10a7616f3cc7'
down_revision = 'c773a35c280f'
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