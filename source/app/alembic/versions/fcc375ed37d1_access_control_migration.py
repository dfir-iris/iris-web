"""Access control migration

Revision ID: fcc375ed37d1
Revises: 7cc588444b79
Create Date: 2022-06-14 17:01:29.205520

"""
import sqlalchemy as sa
import uuid
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.alembic.alembic_utils import _has_table

# revision identifiers, used by Alembic.
revision = 'fcc375ed37d1'
down_revision = '7cc588444b79'
branch_labels = None
depends_on = None


def upgrade():

    # Add all the new access control tables if they don't exist
    if not _has_table('user_case_access'):
        op.create_table('user_case_access',
                        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
                        sa.Column('case_id', sa.BigInteger(), sa.ForeignKey('cases.case_id'), nullable=False),
                        keep_existing=True
                        )

    if not _has_table('group_case_access'):
        op.create_table('group_case_access',
                        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('group_id', sa.BigInteger(), sa.ForeignKey('groups.group_id'), nullable=False),
                        sa.Column('case_id', sa.BigInteger(), sa.ForeignKey('cases.case_id'), nullable=False),
                        sa.Column('access_level', sa.BigInteger(), nullable=False),
                        keep_existing=True
                        )

    if not _has_table('groups'):
        op.create_table('groups',
                        sa.Column('group_id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('group_uuid', UUID(as_uuid=True), default=uuid.uuid4, nullable=False),
                        sa.Column('group_name', sa.Text(), nullable=False),
                        sa.Column('group_description', sa.Text(), nullable=False),
                        sa.Column('group_permissions', sa.Text(), nullable=False),
                        keep_existing=True
                        )

    if not _has_table('organization_case_access'):
        op.create_table('organization_case_access',
                        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('org_id', sa.BigInteger(), sa.ForeignKey('organizations.org_id'), nullable=False),
                        sa.Column('case_id', sa.BigInteger(), sa.ForeignKey('cases.case_id'), nullable=False),
                        sa.Column('access_level', sa.BigInteger(), nullable=False),
                        keep_existing=True
                        )

    if not _has_table('organizations'):
        op.create_table('organizations',
                        sa.Column('org_id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('org_uuid', UUID(as_uuid=True), default=uuid.uuid4, nullable=False),
                        sa.Column('org_name', sa.Text(), nullable=False),
                        sa.Column('org_description', sa.Text(), nullable=False),
                        sa.Column('org_url', sa.Text(), nullable=False),
                        sa.Column('org_email', sa.Text(), nullable=False),
                        sa.Column('org_logo', sa.Text(), nullable=False),
                        sa.Column('org_type', sa.Text(), nullable=False),
                        sa.Column('org_sector', sa.Text(), nullable=False),
                        sa.Column('org_nationality', sa.Text(), nullable=False),
                        keep_existing=True
                        )

    if not _has_table('user_organisation'):
        op.create_table('user_organisation',
                        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
                        sa.Column('org_id', sa.BigInteger(), sa.ForeignKey('organizations.org_id'), nullable=False),
                        keep_existing=True
                        )

    # Migrate the users to the new access control system
    conn = op.get_bind()
    res = conn.execute(f"select id from user where task_status = '{update}';")
    results = res.fetchall()
    res = conn.execute(f"select id from task_status where status_name = '{update}';")
    e_info = res.fetchall()

    if e_info:
        status_id = e_info[0][0]

        for res in results:
            conn.execute(t_tasks.update().where(t_tasks.c.id == res[0]).values(
                task_status_id=status_id
            ))

    pass


def downgrade():
    pass
