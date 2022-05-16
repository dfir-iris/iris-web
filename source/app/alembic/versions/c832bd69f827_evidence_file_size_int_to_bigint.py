"""Evidence file_size int to bigint

Revision ID: c832bd69f827
Revises: b664ca1203a4
Create Date: 2022-04-11 21:49:30.739817

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'c832bd69f827'
down_revision = 'b664ca1203a4'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('case_received_file', 'file_size',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)
    pass


def downgrade():
    pass
