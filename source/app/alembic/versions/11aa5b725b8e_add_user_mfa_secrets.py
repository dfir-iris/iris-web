"""Add user MFA secrets

Revision ID: 11aa5b725b8e
Revises: 9e4947a207a6
Create Date: 2024-05-23 08:04:33.045401

"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = '11aa5b725b8e'
down_revision = '9e4947a207a6'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('user', 'mfa_secrets'):
        op.add_column('user',
                      sa.Column('mfa_secrets', sa.Text, nullable=True)
                      )

    if not _table_has_column('user', 'webauthn_credentials'):
        op.add_column('user',
                      sa.Column('webauthn_credentials', sa.JSON, nullable=True)
                      )
    pass


def downgrade():
    pass
