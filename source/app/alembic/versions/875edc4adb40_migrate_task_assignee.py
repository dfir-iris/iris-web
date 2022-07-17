"""Modifying case tasks to remove assignee id for instead, adding a table named task_assignee

Revision ID: 875edc4adb40
Revises: fcc375ed37d1
Create Date: 2022-07-17 14:57:22.809977

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
from sqlalchemy import engine_from_config
from sqlalchemy.engine import reflection

from app.alembic.alembic_utils import _has_table

revision = '875edc4adb40'
down_revision = 'fcc375ed37d1'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # Get all users with their roles
    if _has_table("case_tasks"):
        if _table_has_column("case_tasks", "task_assignee_id"):
            res = conn.execute(f"select id, task_assignee_id from case_tasks")
            results_tasks = res.fetchall()

            for task in results_tasks:
                task_id = task[0]
                user_id = task[1]
                # Migrate assignees to task_assignee
                conn.execute(f"insert into task_assignee (user_id, task_id) values ({user_id}, {task_id}) "
                             f"on conflict do nothing;")

            op.drop_column(
                table_name='case_tasks',
                column_name='task_assignee_id'
            )


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
