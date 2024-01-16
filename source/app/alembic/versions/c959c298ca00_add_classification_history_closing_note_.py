"""Add classification, history, closing note and initial date

Revision ID: c959c298ca00
Revises: 4ecdfcb34f7c
Create Date: 2023-03-03 23:49:16.360494

"""
import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

from app.alembic.alembic_utils import _table_has_column, _has_table

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
        sa.Column('owner_id', sa.Integer, sa.ForeignKey('user.id'), nullable=False),
        sa.Column('classification_id', sa.Integer, sa.ForeignKey('case_classification.id'), nullable=False)
    )
    res = conn.execute(text(f"select case_id, open_date, user_id from \"cases\";"))
    results = res.fetchall()

    ras = conn.execute(text(f"select id from \"user\" ORDER BY id ASC LIMIT 1;"))
    user = ras.fetchone()

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

    if not _has_table('case_classification'):

        op.create_table('case_classification',
                        sa.MetaData(),
                        sa.Column('id', sa.Integer, primary_key=True),
                        sa.Column('name', sa.Text),
                        sa.Column('name_expanded', sa.Text),
                        sa.Column('creation_date', sa.DateTime, server_default=text("now()"), nullable=True),
                        sa.Column('created_by', sa.ForeignKey('user.id'), nullable=True)
                        )

        op.create_foreign_key('fk_case_classification_user_id', 'case_classification', 'user', ['created_by'], ['id'])

    if not _table_has_column('cases', 'classification_id'):

        classification_table = sa.Table(
            'case_classification',
            sa.MetaData(),
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('name', sa.Text),
            sa.Column('name_expanded', sa.Text),
            sa.Column('creation_date', sa.DateTime, server_default=text("now()"), nullable=True),
            sa.Column('created_by', sa.ForeignKey('user.id'), nullable=True),
            keep_existing=True
        )
        other_classification = sa.select([classification_table.c.id]).where(
            classification_table.c.name == 'other:other')

        if conn.execute(other_classification).fetchone() is None:
            # Create other:other for migration - the rest of the data will be handled by post init
            op.execute(text(f"insert into case_classification (name, name_expanded, description, created_by_id) "
                       f"values ('other:other', 'Other: Other', 'All incidents that do not fit in one of the given "
                       f"categories should be put into this class. If the number of incidents in this category "
                       f"increases, it is an indicator that the classification scheme must be revised.', {user[0]});"))

            other_classification = sa.select([classification_table.c.id]).where(
                classification_table.c.name == 'other:other')
            other_classification_id = conn.execute(other_classification).fetchone()[0]

        else:
            other_classification_id = conn.execute(other_classification).fetchone()[0]

        op.add_column('cases',
                      sa.Column('classification_id', sa.Integer, sa.ForeignKey('case_classification.id'),
                                server_default=text(str(other_classification_id))),
                      )

        cid_list = [c[0] for c in results]

        op.execute(cases_table.update().where(cases_table.c.case_id.in_(cid_list)).values(
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
