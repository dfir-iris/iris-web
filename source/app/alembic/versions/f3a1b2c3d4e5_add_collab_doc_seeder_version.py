"""Add seeder_version to collab_doc.

Rows persisted by an older markdown→Y.Doc seeder need to be
re-seeded when the parser learns to handle a new block type (tables
were the first case — the CommonMark parser silently dropped GFM
tables, so any legacy note with a table lost its tabular structure
after the first open). The version column lets `ensure_snapshot`
detect stale rows and re-seed them from the source column instead
of returning the lossy y_state.

Existing rows default to `0`; the current seeder version lives in
`_CURRENT_SEEDER_VERSION` in `business/collab.py`.

Idempotent via `_table_has_column`.

Revision ID: f3a1b2c3d4e5
Revises: e2f3g4h5i6j7
Create Date: 2026-07-07 13:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _has_table
from app.alembic.alembic_utils import _table_has_column


revision = 'f3a1b2c3d4e5'
down_revision = 'e2f3g4h5i6j7'
branch_labels = None
depends_on = None


def upgrade():
    if not _has_table('collab_doc'):
        return
    if _table_has_column('collab_doc', 'seeder_version'):
        return
    op.add_column(
        'collab_doc',
        sa.Column('seeder_version', sa.Integer(), nullable=True),
    )


def downgrade():
    if _has_table('collab_doc') and _table_has_column(
        'collab_doc', 'seeder_version'
    ):
        op.drop_column('collab_doc', 'seeder_version')
