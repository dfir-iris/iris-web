"""Add indexes to cases table

Revision ID: a1b2c3d4e5f6
Revises: f0e1d2c3b4a5
Create Date: 2026-05-06

"""
from alembic import op
from sqlalchemy import text

revision = 'a1b2c3d4e5f6'
down_revision = 'f0e1d2c3b4a5'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_cases_user_id
        ON cases (user_id)
    """))
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_cases_state_id
        ON cases (state_id)
    """))


def downgrade():
    op.execute(text("DROP INDEX IF EXISTS idx_cases_user_id"))
    op.execute(text("DROP INDEX IF EXISTS idx_cases_state_id"))