"""Add IocType validation

Revision ID: ad4e0cd17597
Revises: cd519d2d24df
Create Date: 2022-08-04 15:37:44.484997

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
from sqlalchemy import engine_from_config
from sqlalchemy.engine import reflection

revision = 'ad4e0cd17597'
down_revision = 'cd519d2d24df'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('ioc_type', 'type_validation_regex'):
        op.add_column('ioc_type',
                      sa.Column('type_validation_regex', sa.String(255))
                      )

    if not _table_has_column('ioc_type', 'type_validation_expect'):
        op.add_column('ioc_type',
                      sa.Column('type_validation_expect', sa.String(255))
                      )


def downgrade():
    op.drop_column('ioc_type', 'type_validation_regex')


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
