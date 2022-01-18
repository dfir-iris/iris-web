"""Update tasks status

Revision ID: c773a35c280f
Revises: 0db700644a4f
Create Date: 2022-01-18 07:51:43.714021

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy import engine_from_config
from sqlalchemy.engine import reflection

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

    if _table_has_column('case_tasks', 'task_status_id'):
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
            res = conn.execute(f"select id from case_tasks where task_status = '{update}';")
            results = res.fetchall()
            res = conn.execute(f"select id from task_status where status_name = '{update}';")
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

    pass


def downgrade():
    pass


def _table_has_column(table, column):
    config = op.get_context().config
    engine = engine_from_config(
        config.get_section(config.config_ini_section), prefix='sqlalchemy.')
    insp = reflection.Inspector.from_engine(engine)
    has_column = False

    for col in insp.get_columns(table):
        if column != col['name']:
            continue
        has_column = True
    return has_column