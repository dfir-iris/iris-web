"""Add cluster scope to comments.

Mirrors the alert path (`comment_alert_id`) so alert clusters can carry a
first-class analyst comment stream, feeding the cluster detail
Activity tab.

Revision ID: c8f3a2d47b19
Revises: b2d0e8a9f4c1
Create Date: 2026-07-02 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column


revision = 'c8f3a2d47b19'
down_revision = 'b2d0e8a9f4c1'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('comments', 'comment_cluster_id'):
        op.add_column(
            'comments',
            sa.Column('comment_cluster_id', sa.BigInteger(), nullable=True),
        )
        op.create_foreign_key(
            'fk_comments_cluster_id',
            'comments', 'alert_clusters',
            ['comment_cluster_id'], ['cluster_id'],
        )


def downgrade():
    op.drop_constraint('fk_comments_cluster_id', 'comments', type_='foreignkey')
    op.drop_column('comments', 'comment_cluster_id')
