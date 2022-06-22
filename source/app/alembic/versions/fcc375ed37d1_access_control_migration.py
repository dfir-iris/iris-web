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
from app.iris_engine.access_control.utils import ac_get_mask_analyst
from app.iris_engine.access_control.utils import ac_get_mask_case_access_level_full
from app.iris_engine.access_control.utils import ac_get_mask_full_permissions

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
        op.create_foreign_key('fk_user_case_access_user_id', 'user_case_access', 'user', ['user_id'], ['id'])
        op.create_foreign_key('fk_user_case_access_case_id', 'user_case_access', 'cases', ['case_id'], ['case_id'])
        op.create_unique_constraint('uq_user_case_access_user_id_case_id', 'user_case_access', ['user_id', 'case_id'])

    if not _has_table('group_case_access'):
        op.create_table('group_case_access',
                        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('group_id', sa.BigInteger(), sa.ForeignKey('groups.group_id'), nullable=False),
                        sa.Column('case_id', sa.BigInteger(), sa.ForeignKey('cases.case_id'), nullable=False),
                        sa.Column('access_level', sa.BigInteger(), nullable=False),
                        keep_existing=True
                        )
        op.create_foreign_key('group_case_access_group_id_fkey', 'group_case_access', 'groups',
                              ['group_id'], ['group_id'])
        op.create_foreign_key('group_case_access_case_id_fkey', 'group_case_access', 'cases',
                              ['case_id'], ['case_id'])
        op.create_unique_constraint('group_case_access_unique', 'group_case_access', ['group_id', 'case_id'])

    if not _has_table('groups'):
        op.create_table('groups',
                        sa.Column('group_id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('group_uuid', UUID(as_uuid=True), default=uuid.uuid4, nullable=False),
                        sa.Column('group_name', sa.Text(), nullable=False),
                        sa.Column('group_description', sa.Text(), nullable=False),
                        sa.Column('group_permissions', sa.BigInteger(), nullable=False),
                        keep_existing=True
                        )
        op.create_unique_constraint('groups_group_name_unique', 'groups', ['group_name'])

    if not _has_table('organisations'):
        op.create_table('organisations',
                        sa.Column('org_id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('org_uuid', UUID(as_uuid=True), default=uuid.uuid4(), nullable=False),
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
        op.create_unique_constraint('organisation_name_unique', 'organisations', ['org_name'])

    if not _has_table('organisation_case_access'):
        op.create_table('organisation_case_access',
                        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('org_id', sa.BigInteger(), sa.ForeignKey('organisations.org_id'), nullable=False),
                        sa.Column('case_id', sa.BigInteger(), sa.ForeignKey('cases.case_id'), nullable=False),
                        sa.Column('access_level', sa.BigInteger(), nullable=False),
                        keep_existing=True
                        )
        op.create_foreign_key('organisation_case_access_org_id_fkey', 'organisation_case_access',
                              'organisations', ['org_id'], ['org_id'])
        op.create_foreign_key('organisation_case_access_case_id_fkey', 'organisation_case_access', 'cases',
                              ['case_id'], ['case_id'])
        op.create_unique_constraint('organisation_case_access_unique', 'organisation_case_access',
                                    ['org_id', 'case_id'])

    if not _has_table('user_organisation'):
        op.create_table('user_organisation',
                        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
                        sa.Column('org_id', sa.BigInteger(), sa.ForeignKey('organisations.org_id'), nullable=False),
                        keep_existing=True
                        )
        op.create_foreign_key('user_organisation_user_id_fkey', 'user_organisation', 'user', ['user_id'], ['id'])
        op.create_foreign_key('user_organisation_org_id_fkey', 'user_organisation', 'organisations',
                              ['org_id'], ['org_id'])
        op.create_unique_constraint('user_organisation_unique', 'user_organisation', ['user_id', 'org_id'])

    if not _has_table('user_group'):
        op.create_table('user_group',
                        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
                        sa.Column('group_id', sa.BigInteger(), sa.ForeignKey('groups.group_id'), nullable=False),
                        keep_existing=True
                        )
        op.create_foreign_key('user_group_user_id_fkey', 'user_group', 'user', ['user_id'], ['id'])
        op.create_foreign_key('user_group_group_id_fkey', 'user_group', 'groups', ['group_id'], ['group_id'])
        op.create_unique_constraint('user_group_unique', 'user_group', ['user_id', 'group_id'])

    # Create the groups if they don't exist
    conn = op.get_bind()
    res = conn.execute(f"select group_id from groups where group_name = 'Administrators';")
    if res.rowcount == 0:
        conn.execute(f"insert into groups (group_name, group_description, group_permissions, group_uuid) "
                     f"values ('Administrators', 'Administrators', '{ac_get_mask_full_permissions()}', '{uuid.uuid4()}');")
        res = conn.execute(f"select group_id from groups where group_name = 'Administrators';")
    admin_group_id = res.fetchone()[0]

    res = conn.execute(f"select group_id from groups where group_name = 'Analysts';")
    if res.rowcount == 0:
        conn.execute(f"insert into groups (group_name, group_description, group_permissions, group_uuid) "
                     f"values ('Analysts', 'Standard Analysts', '{ac_get_mask_analyst()}', '{uuid.uuid4()}');")
        res = conn.execute(f"select group_id from groups where group_name = 'Analysts';")

    analyst_group_id = res.fetchone()[0]

    # Create the organisations if they don't exist
    res = conn.execute(f"select org_id from organisations where org_name = 'Default Org';")
    if res.rowcount == 0:
        conn.execute(f"insert into organisations (org_name, org_description, org_url, org_email, org_logo, "
                     f"org_type, org_sector, org_nationality, org_uuid) values ('Default Org', 'Default Organisation', "
                     f"'', '', "
                     f"'','', '', '', '{uuid.uuid4()}');")
        res = conn.execute(f"select org_id from organisations where org_name = 'Default Org';")
    default_org_id = res.fetchone()[0]

    # Give the organisation access to all the cases
    res = conn.execute(f"select case_id from cases;")
    result_cases = res.fetchall()
    access_level = ac_get_mask_case_access_level_full()
    for case_id in result_cases:
        conn.execute(f"insert into organisation_case_access (org_id, case_id, access_level) values "
                     f"('{default_org_id},{case_id}, {access_level}")

    # Migrate the users to the new access control system
    conn = op.get_bind()

    # Get all users with their roles
    res = conn.execute(f"select distinct roles.name, \"user\".id from user_roles INNER JOIN \"roles\" ON "
                       f"\"roles\".id = user_roles.role_id INNER JOIN \"user\" ON \"user\".id = user_roles.user_id;")
    results_users = res.fetchall()

    for user_id in results_users:
        role_name = user_id[0]
        user_id = user_id[1]
        # Migrate user to groups
        if role_name == 'administrator':
            conn.execute(f"insert into user_group (user_id, group_id) values ({user_id}, {admin_group_id});")

        elif role_name == 'investigator':
            conn.execute(f"insert into user_group (user_id, group_id) values ({user_id}, {analyst_group_id});")

        # Add user to default organisation
        conn.execute(f"insert into user_organisation (user_id, org_id) values ({user_id}, {default_org_id});")

    pass


def downgrade():
    pass
