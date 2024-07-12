"""Add user MFA secrets

Revision ID: 11aa5b725b8e
Revises: 9e4947a207a6
Create Date: 2024-05-23 08:04:33.045401

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = '11aa5b725b8e'
down_revision = '9e4947a207a6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('COMMIT')

    if not _table_has_column('user', 'mfa_secrets'):
        op.add_column('user', sa.Column('mfa_secrets', sa.Text, nullable=True))

    if not _table_has_column('user', 'webauthn_credentials'):
        op.add_column('user', sa.Column('webauthn_credentials', sa.JSON, nullable=True))

    if not _table_has_column('user', 'mfa_setup_complete'):
        op.add_column('user', sa.Column('mfa_setup_complete', sa.Boolean, nullable=False,
                                        server_default=text("FALSE")))

    if not _table_has_column('server_settings', 'enforce_mfa'):
        op.add_column('server_settings', sa.Column('enforce_mfa', sa.Boolean, default=False))

    return


def downgrade():
    pass
