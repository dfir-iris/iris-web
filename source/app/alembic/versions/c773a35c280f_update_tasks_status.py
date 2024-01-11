"""Update tasks status

Revision ID: c773a35c280f
Revises: 0db700644a4f
Create Date: 2022-01-18 07:51:43.714021

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.

revision = 'c773a35c280f'
down_revision = '0db700644a4f'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('case_tasks', 'task_status_id'):
        op.add_column('case_tasks',
                      sa.Column('task_status_id', sa.Integer, sa.ForeignKey('task_status.id'))
                      )

        # Add the foreign key of ioc_type to ioc
        op.create_foreign_key(
            constraint_name='task_task_status_id',
            source_table="case_tasks",
            referent_table="task_status",
            local_cols=["task_status_id"],
            remote_cols=["id"])

    if _table_has_column('case_tasks', 'task_status'):
        # Set schema and make migration of data
        t_tasks = sa.Table(
            'case_tasks',
            sa.MetaData(),
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('task_title', sa.Text),
            sa.Column('task_status', sa.Text),
            sa.Column('task_status_id', sa.ForeignKey('task_status.id')),
        )
        to_update = ['To do', 'In progress', 'On hold', 'Done', 'Canceled']

        # Migrate existing IOCs
        for update in to_update:
            conn = op.get_bind()
            res = conn.execute(text(f"select id from case_tasks where task_status = '{update}';"))
            results = res.fetchall()
            res = conn.execute(text(f"select id from task_status where status_name = '{update}';"))
            e_info = res.fetchall()

            if e_info:
                status_id = e_info[0][0]

                for res in results:
                    conn.execute(t_tasks.update().where(t_tasks.c.id == res[0]).values(
                        task_status_id=status_id
                    ))

        op.drop_column(
            table_name='case_tasks',
            column_name='task_status'
        )

    if not _table_has_column('global_tasks', 'task_status_id'):
        op.add_column('global_tasks',
                      sa.Column('task_status_id', sa.Integer, sa.ForeignKey('task_status.id'))
                      )

        # Add the foreign key of ioc_type to ioc
        op.create_foreign_key(
            constraint_name='global_task_status_id',
            source_table="global_tasks",
            referent_table="task_status",
            local_cols=["task_status_id"],
            remote_cols=["id"])

    if _table_has_column('global_tasks', 'task_status'):
        # Set schema and make migration of data
        tg_tasks = sa.Table(
            'global_tasks',
            sa.MetaData(),
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('task_title', sa.Text),
            sa.Column('task_status', sa.Text),
            sa.Column('task_status_id', sa.ForeignKey('task_status.id')),
        )
        to_update = ['To do', 'In progress', 'On hold', 'Done', 'Canceled']

        # Migrate existing IOCs
        for update in to_update:
            conn = op.get_bind()
            res = conn.execute(text(f"select id from global_tasks where task_status = '{update}';"))
            results = res.fetchall()
            res = conn.execute(text(f"select id from task_status where status_name = '{update}';"))
            e_info = res.fetchall()

            if e_info:
                status_id = e_info[0][0]

                for res in results:
                    conn.execute(tg_tasks.update().where(tg_tasks.c.id == res[0]).values(
                        task_status_id=status_id
                    ))

        op.drop_column(
            table_name='global_tasks',
            column_name='task_status'
        )

    pass


def downgrade():
    pass
