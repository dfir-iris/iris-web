"""Add indexes to user_case_effective_access

Revision ID: a1b2c3d4e5f6
Revises: 79a9a54e8f9d
Create Date: 2026-04-30

"""
from alembic import op

revision = 'f0e1d2c3b4a5'
down_revision = '79a9a54e8f9d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        'idx_user_case_effective_access_user_id',
        'user_case_effective_access',
        ['user_id'],
        if_not_exists=True
    )
    op.create_index(
        'idx_user_case_effective_access_case_id',
        'user_case_effective_access',
        ['case_id'],
        if_not_exists=True
    )


def downgrade():
    op.drop_index('idx_user_case_effective_access_user_id', table_name='user_case_effective_access')
    op.drop_index('idx_user_case_effective_access_case_id', table_name='user_case_effective_access')