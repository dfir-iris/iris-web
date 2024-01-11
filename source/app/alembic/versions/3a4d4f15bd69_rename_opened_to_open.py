"""Rename opened to open

Revision ID: 3a4d4f15bd69
Revises: 65168cb6cc90
Create Date: 2023-10-05 11:36:45.246779

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '3a4d4f15bd69'
down_revision = '65168cb6cc90'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text(
        "UPDATE case_state SET state_name='Open' WHERE state_name='Opened'"
    ))


def downgrade():
    op.execute(text(
        "UPDATE case_state SET state_name='Opened' WHERE state_name='Open'"
    ))
