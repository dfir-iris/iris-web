"""Password policy edition

Revision ID: cd519d2d24df
Revises: ca93d4b54571
Create Date: 2022-05-25 18:09:08.741619

"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.

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
            op.add_column('server_settings',
                          sa.Column(col, columns[col])
                          )

    t_ua = sa.Table(
        'server_settings',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('password_policy_min_length', sa.Integer),
        sa.Column('password_policy_upper_case', sa.Boolean),
        sa.Column('password_policy_lower_case', sa.Boolean),
        sa.Column('password_policy_digit', sa.Boolean),
        sa.Column('password_policy_special_chars', sa.Text)
    )
    conn = op.get_bind()
    conn.execute(t_ua.update().values(
        password_policy_min_length=12,
        password_policy_upper_case=True,
        password_policy_lower_case=True,
        password_policy_digit=True,
        password_policy_special_chars=''
    ))

    pass


def downgrade():
    pass

