"""Add indexes to user_case_effective_access

Revision ID: f0e1d2c3b4a5
Revises: afcff5ebcf7c
Create Date: 2026-04-30

"""
from alembic import op
from sqlalchemy import text

revision = 'f0e1d2c3b4a5'
down_revision = 'afcff5ebcf7c'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'user_case_effective_access'
                AND indexname = 'idx_user_case_effective_access_user_id'
            ) THEN
                CREATE INDEX idx_user_case_effective_access_user_id
                ON user_case_effective_access (user_id);
            END IF;
        END $$;
    """))
    op.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'user_case_effective_access'
                AND indexname = 'idx_user_case_effective_access_case_id'
            ) THEN
                CREATE INDEX idx_user_case_effective_access_case_id
                ON user_case_effective_access (case_id);
            END IF;
        END $$;
    """))


def downgrade():
    op.execute(text("DROP INDEX IF EXISTS idx_user_case_effective_access_user_id"))
    op.execute(text("DROP INDEX IF EXISTS idx_user_case_effective_access_case_id"))