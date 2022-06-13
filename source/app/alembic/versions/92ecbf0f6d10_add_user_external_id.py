"""Add user external ID

Revision ID: 92ecbf0f6d10
Revises: cd519d2d24df
Create Date: 2022-06-13 08:59:04.860887

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy import engine_from_config
from sqlalchemy.engine import reflection

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