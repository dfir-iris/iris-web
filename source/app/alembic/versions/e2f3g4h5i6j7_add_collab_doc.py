"""Add collab_doc table for Yjs snapshots.

Backs the real-time collaborative editor. One row per document
(case note, case summary, war-room note, sitrep); `doc_name` is a
stable string key of the form `<kind>:<id>` — see
`app.models.collab.CollabDoc` for the schema motivation.

Idempotent via `_has_table`.

Revision ID: e2f3g4h5i6j7
Revises: d1e2f3a4b5c6
Create Date: 2026-07-03 15:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _has_table


revision = 'e2f3g4h5i6j7'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade():
    if _has_table('collab_doc'):
        return

    op.create_table(
        'collab_doc',
        sa.Column('doc_name', sa.Text(), nullable=False),
        sa.Column('y_state', sa.LargeBinary(), nullable=True),
        sa.Column('content_md', sa.Text(), nullable=True),
        sa.Column('last_flushed_at', sa.DateTime(), nullable=True),
        sa.Column(
            'updated_by_id', sa.BigInteger(),
            sa.ForeignKey('user.id'), nullable=True,
        ),
        sa.PrimaryKeyConstraint('doc_name'),
    )


def downgrade():
    if _has_table('collab_doc'):
        op.drop_table('collab_doc')
