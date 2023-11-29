"""Add evidence type to evidences

Revision ID: d6c49c5435c2
Revises: 3a4d4f15bd69
Create Date: 2023-11-06 15:29:14.435562

"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = 'd6c49c5435c2'
down_revision = '3a4d4f15bd69'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('case_received_file', 'type_id'):

        op.add_column(
            'case_received_file',
            sa.Column('type_id', sa.Integer, sa.ForeignKey('evidence_type.id'), nullable=True)
        )

        op.create_foreign_key(
            None, 'case_received_file', 'evidence_type', ['type_id'], ['id']
        )

    if not _table_has_column('case_received_file', 'acquisition_date'):

        op.add_column(
            'case_received_file',
            sa.Column('acquisition_date', sa.DateTime, nullable=True),

        )

    if not _table_has_column('case_received_file', 'start_date'):

        op.add_column(
            'case_received_file',
            sa.Column('start_date', sa.DateTime, nullable=True),

        )

    if not _table_has_column('case_received_file', 'end_date'):

        op.add_column(
            'case_received_file',
            sa.Column('end_date', sa.DateTime, nullable=True),

        )

    if not _table_has_column('case_received_file', 'chain_of_custody'):

        op.add_column(
            'case_received_file',
            sa.Column('chain_of_custody', sa.JSON, nullable=True),

        )

    pass


def downgrade():
    pass
