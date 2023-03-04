"""Add classification, history, closing note and initial date

Revision ID: c959c298ca00
Revises: 4ecdfcb34f7c
Create Date: 2023-03-03 23:49:16.360494

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = 'c959c298ca00'
down_revision = '4ecdfcb34f7c'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    cases_table = sa.Table(
        'cases',
        sa.MetaData(),
        sa.Column('case_id', sa.Integer, primary_key=True),
        sa.Column('open_date', sa.DateTime, nullable=False),
        sa.Column('initial_date', sa.DateTime, nullable=False),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('user.id'), nullable=False),
        sa.Column('owner_id', sa.Integer, sa.ForeignKey('user.id'), nullable=False)
    )
    res = conn.execute(f"select case_id, open_date, user_id from \"cases\";")
    results = res.fetchall()

    if not _table_has_column('cases', 'modification_history'):
        op.add_column('cases',
                      sa.Column('modification_history', sa.JSON)
                      )

    if not _table_has_column('cases', 'initial_date'):
        op.add_column('cases',
                      sa.Column('initial_date', sa.DateTime, nullable=False, server_default=sa.text("now()"))
                      )

        for case in results:
            conn.execute(cases_table.update().where(cases_table.c.case_id == case[0]).values(
                initial_date=case[1]
            ))

    if not _table_has_column('cases', 'closing_note'):
        op.add_column('cases',
                      sa.Column('closing_note', sa.Text)
                      )

    if not _table_has_column('cases', 'classification_id'):

        classification_table = sa.Table(
            'case_classification',
            sa.MetaData(),
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('name', sa.Text, nullable=False)
        )

        other_classification = sa.select([classification_table.c.id]).where(
            classification_table.c.name == 'other:other')

        other_classification_id = conn.execute(other_classification).fetchone()[0]

        op.add_column('cases',
                      sa.Column('classification_id', sa.Integer, sa.ForeignKey('case_classification.id'),
                                server_default=text("0")),
                      )

        for case in results:
            conn.execute(cases_table.update().where(cases_table.c.case_id == case[0]).values(
                classification_id=other_classification_id
            ))

    if not _table_has_column('cases', 'owner_id'):
        op.add_column('cases',
                      sa.Column('owner_id', sa.Integer, sa.ForeignKey('user.id'),
                                server_default=text("1")),
                      )
        for case in results:
            conn.execute(cases_table.update().where(cases_table.c.case_id == case[0]).values(
                owner_id=case[2]
            ))


def downgrade():
    pass
