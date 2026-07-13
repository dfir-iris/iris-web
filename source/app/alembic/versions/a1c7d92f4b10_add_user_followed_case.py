"""Add user_followed_case join table.

Per-user "follow case" preference: each row links a user to a case the
user wants surfaced on their dashboard regardless of ownership. The
table is intentionally narrow — just the FK pair, a timestamp, and a
unique constraint — because follower-only metadata (notification
preferences, mute, etc.) is intentionally out of scope.

ON DELETE CASCADE on both FKs so that deleting a user or a case
doesn't leave dangling follow rows pointing nowhere.

Revision ID: a1c7d92f4b10
Revises: e9b5f3d20a44
Create Date: 2026-06-27 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _has_table
from app.alembic.alembic_utils import index_exists


revision = 'a1c7d92f4b10'
down_revision = 'e9b5f3d20a44'
branch_labels = None
depends_on = None


def upgrade():
    if not _has_table('user_followed_case'):
        op.create_table(
            'user_followed_case',
            sa.Column('user_id', sa.BigInteger(), nullable=False),
            sa.Column('case_id', sa.BigInteger(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('now()')),
            sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('user_id', 'case_id'),
            sa.UniqueConstraint('user_id', 'case_id',
                                name='uq_user_followed_case_user_case'),
        )
    # Helps the "followers of this case" query (case detail page count).
    if not index_exists('user_followed_case', 'ix_user_followed_case_case_id'):
        op.create_index('ix_user_followed_case_case_id', 'user_followed_case', ['case_id'])


def downgrade():
    if index_exists('user_followed_case', 'ix_user_followed_case_case_id'):
        op.drop_index('ix_user_followed_case_case_id', table_name='user_followed_case')
    if _has_table('user_followed_case'):
        op.drop_table('user_followed_case')
