"""Reviewer in case

Revision ID: 65168cb6cc90
Revises: e33dd011fb87
Create Date: 2023-07-09 09:01:39.243870

"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = '65168cb6cc90'
down_revision = 'e33dd011fb87'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('cases', 'reviewer_id'):
        op.add_column('cases',
                      sa.Column('reviewer_id', sa.Integer(), nullable=True)
                      )

        op.create_foreign_key('fkey_cases_reviewer_id', 'cases', 'user', ['reviewer_id'], ['id'])

    if not _table_has_column('cases', 'review_status_id'):
        op.add_column('cases',
                      sa.Column('review_status_id', sa.Integer(), nullable=True)
                      )

        op.create_foreign_key('fkey_cases_review_status_id', 'cases', 'review_status', ['review_status_id'], ['id'])

    pass


def downgrade():
    pass
