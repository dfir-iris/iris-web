"""Add per-user avatar columns to the user table.

Stores the uploaded profile picture as a bytes blob on the user row.
We picked the LargeBinary column over a filesystem path so that:

* a single Postgres backup captures the avatar with the user that owns
  it (no second restore step, no race between row & file);
* a non-existent file can't desynchronise with a stale DB pointer;
* the bytes are gated by the same auth pipeline as everything else —
  there is no `/static/avatars` directory to leak through a misconfig.

Uploads are normalised to a 256×256 PNG by the route handler before
hitting the column, so the row growth is bounded (~30–80 KB per
avatar) and the schema doesn't need to track MIME type beyond a
sanity-check column.

Revision ID: e9b5f3d20a44
Revises: d8a2f6e91c12
Create Date: 2026-06-26 11:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column


revision = 'e9b5f3d20a44'
down_revision = 'd8a2f6e91c12'
branch_labels = None
depends_on = None


def upgrade():
    # `_table_has_column` makes the upgrade re-runnable. Helpful for
    # deployments that hand-applied the columns ahead of the migration
    # being merged, and for downgrade → upgrade cycles during dev.
    if not _table_has_column('user', 'avatar_blob'):
        op.add_column('user', sa.Column('avatar_blob', sa.LargeBinary(), nullable=True))

    if not _table_has_column('user', 'avatar_mime'):
        op.add_column('user', sa.Column('avatar_mime', sa.String(length=64), nullable=True))

    if not _table_has_column('user', 'avatar_updated_at'):
        op.add_column(
            'user',
            sa.Column('avatar_updated_at', sa.DateTime(), nullable=True),
        )


def downgrade():
    # Drop only what we added. Idempotent guards mirror the upgrade so
    # a partial downgrade can be re-run cleanly.
    if _table_has_column('user', 'avatar_updated_at'):
        op.drop_column('user', 'avatar_updated_at')

    if _table_has_column('user', 'avatar_mime'):
        op.drop_column('user', 'avatar_mime')

    if _table_has_column('user', 'avatar_blob'):
        op.drop_column('user', 'avatar_blob')
