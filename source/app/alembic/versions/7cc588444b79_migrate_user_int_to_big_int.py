"""Migrate user int to big int

Revision ID: 7cc588444b79
Revises: 92ecbf0f6d10
Create Date: 2022-06-14 08:28:59.027411

"""
import uuid

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID

from app.alembic.alembic_utils import _table_has_column

revision = '7cc588444b79'
down_revision = '92ecbf0f6d10'
branch_labels = None
depends_on = None


def upgrade():
    # Upgrade to big integers
    op.alter_column('cases', 'case_id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    if not _table_has_column('cases', 'case_uuid'):
        op.add_column('cases',
                      sa.Column('case_uuid', UUID(as_uuid=True), server_default=text("gen_random_uuid()"),
                                nullable=False)
                      )

    pass


def downgrade():
    pass
