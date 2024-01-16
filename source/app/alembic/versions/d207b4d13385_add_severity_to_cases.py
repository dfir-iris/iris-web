"""Add severity to cases

Revision ID: d207b4d13385
Revises: d6c49c5435c2
Create Date: 2023-11-28 11:50:08.136090

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = 'd207b4d13385'
down_revision = 'd6c49c5435c2'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('cases', 'severity_id'):
        op.add_column(
            'cases',
            sa.Column('severity_id', sa.Integer, sa.ForeignKey('severities.severity_id'), nullable=True)
        )

        op.create_foreign_key(
            None, 'cases', 'severities', ['severity_id'], ['severity_id']
        )

    conn = op.get_bind()
    # Create the new severity if it doesn't exist already - we check first
    res = conn.execute(text(
        "SELECT severity_id FROM severities WHERE severity_name = 'Medium'"
    )).fetchone()

    if res is None:
        conn.execute(text(
            "INSERT INTO severities (severity_name, severity_description) VALUES ('Medium', 'Medium')"
        ))

    # Update the severity of all cases to the default severity
    conn.execute(text(
        "UPDATE cases SET severity_id = (SELECT severity_id FROM severities WHERE severity_name = 'Medium')"
    ))

    pass


def downgrade():
    pass
