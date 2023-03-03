"""Add classification, history, closing note and initial date

Revision ID: c959c298ca00
Revises: 4ecdfcb34f7c
Create Date: 2023-03-03 23:49:16.360494

"""
from alembic import op
import sqlalchemy as sa
from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = 'c959c298ca00'
down_revision = '4ecdfcb34f7c'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('cases', 'modification_history'):
        op.add_column('cases',
                      sa.Column('modification_history', sa.JSON)
                      )

    if not _table_has_column('cases', 'initial_date'):
        op.add_column('cases',
                      sa.Column('initial_date', sa.DateTime, nullable=False, server_default=sa.text("now()"))
                      )

    if not _table_has_column('cases', 'closing_note'):
        op.add_column('cases',
                      sa.Column('closing_note', sa.Text)
                      )

    if not _table_has_column('cases', 'classification_id'):
        op.add_column('cases',
                      sa.Column('classification_id', sa.Integer, sa.ForeignKey('case_classification.id'))
                      )

    pass


def downgrade():
    pass
