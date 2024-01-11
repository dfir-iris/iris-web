"""Add case state

Revision ID: 2604f6962838
Revises: db93d5c4c0aa
Create Date: 2023-05-05 11:16:19.997383

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

from app.models.cases import CaseState


from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = '2604f6962838'
down_revision = 'db93d5c4c0aa'
branch_labels = None
depends_on = None


def upgrade():
    # Add the state_id column to the cases table
    if not _table_has_column('cases', 'state_id'):

        state_id = 1
        state = CaseState.query.filter_by(state_id=state_id).first()

        if state is None:
            state = CaseState()
            state.id=state_id
            state.state_name='Unspecified'
            state.state_description='Unspecified'
            state.protected=True

            op.bulk_insert(CaseState.__table__, [state.__dict__])

        op.add_column(
            'cases',
            sa.Column('state_id', sa.Integer, sa.ForeignKey('case_state.state_id'), nullable=True,
                      server_default=sa.text("1"))
        )

        # Set the default value for the state_id column
        op.execute(text("UPDATE cases SET state_id = 1"))

        # Create a foreign key constraint between cases.state_id and case_state.state_id
        op.create_foreign_key(
            None, 'cases', 'case_state', ['state_id'], ['state_id']
        )


def downgrade():
    pass
