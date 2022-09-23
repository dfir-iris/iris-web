"""Objects UUID field

Revision ID: 20447ecb2245
Revises: ad4e0cd17597
Create Date: 2022-09-23 21:07:20.007874

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID

from app.alembic.alembic_utils import _table_has_column

revision = '20447ecb2245'
down_revision = 'ad4e0cd17597'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('cases', 'case_id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    if not _table_has_column('cases', 'case_uuid'):
        op.add_column('cases',
                      sa.Column('case_uuid', UUID(as_uuid=True), server_default=text("gen_random_uuid()"),
                                nullable=False)
                      )

    op.alter_column('cases_events', 'event_id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    if not _table_has_column('cases_events', 'event_uuid'):
        op.add_column('cases_events',
                      sa.Column('event_uuid', UUID(as_uuid=True), server_default=text("gen_random_uuid()"),
                                nullable=False)
                      )

    pass


def downgrade():
    pass
