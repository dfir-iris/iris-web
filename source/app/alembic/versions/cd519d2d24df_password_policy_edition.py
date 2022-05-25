"""Password policy edition

Revision ID: cd519d2d24df
Revises: ca93d4b54571
Create Date: 2022-05-25 18:09:08.741619

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy import engine_from_config
from sqlalchemy.engine import reflection

revision = 'cd519d2d24df'
down_revision = 'ca93d4b54571'
branch_labels = None
depends_on = None


def upgrade():
    columns = {
        "password_policy_min_length": sa.Integer,
        "password_policy_upper_case": sa.Boolean,
        "password_policy_lower_case": sa.Boolean,
        "password_policy_digit": sa.Boolean,
        "password_policy_special_chars": sa.Text,
    }

    for col in columns:
        if not _table_has_column('server_settings', col):
            op.add_column('cases_events',
                          sa.Column(col, columns[col])
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