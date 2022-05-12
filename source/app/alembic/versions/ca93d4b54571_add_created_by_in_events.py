"""Add created by in events

Revision ID: ca93d4b54571
Revises: 79a9a54e8f9d
Create Date: 2022-05-08 14:58:38.839651

"""
import sqlalchemy as sa
from alembic import op
# revision identifiers, used by Alembic.
from sqlalchemy import engine_from_config
from sqlalchemy.engine import reflection

revision = 'ca93d4b54571'
down_revision = '79a9a54e8f9d'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('cases_events', 'modification_history'):
        op.add_column('cases_events',
                      sa.Column('modification_history', sa.JSON)
                      )
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