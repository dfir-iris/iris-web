"""Add alert in comments

Revision ID: f727badcc4e1
Revises: 50f28953a485
Create Date: 2023-04-12 09:28:58.993723

"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = 'f727badcc4e1'
down_revision = '50f28953a485'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column("comments", "comment_alert_id"):
        op.add_column('comments',
                      sa.Column('comment_alert_id',
                                sa.BigInteger(), nullable=True)
                  )

        op.create_foreign_key(None,
                              'comments', 'alerts',
                              ['comment_alert_id'], ['alert_id'])


def downgrade():
    op.drop_constraint(None, 'comments', type_='foreignkey')
    op.drop_column('comments', 'comment_alert_id')
    pass
