"""Access control migration

Revision ID: fcc375ed37d1
Revises: 7cc588444b79
Create Date: 2022-06-14 17:01:29.205520

"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID

from app.alembic.alembic_utils import _has_table
# revision identifiers, used by Alembic.
from app.alembic.alembic_utils import _table_has_column
from app.iris_engine.access_control.utils import ac_get_mask_analyst
from app.iris_engine.access_control.utils import ac_get_mask_case_access_level_full
from app.iris_engine.access_control.utils import ac_get_mask_full_permissions

revision = 'fcc375ed37d1'
down_revision = '7cc588444b79'
branch_labels = None
depends_on = None


def upgrade():
    # Ensure the DB is not in a locked state and commit any pending transactions
    op.execute(text("COMMIT;"))

    conn = None
    # Add UUID to users
    if not _table_has_column('user', 'uuid'):
        conn = op.get_bind()
        op.add_column('user',
                      sa.Column('uuid', UUID(as_uuid=True), default=uuid.uuid4, nullable=False,
                                server_default=sa.text('gen_random_uuid()'))
                      )

        # Add UUID to existing users
        t_users = sa.Table(
            'user',
            sa.MetaData(),
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('uuid',  UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
        )

        res = conn.execute(text(f"select id from \"user\";"))
        results = res.fetchall()
        for user in results:
            conn.execute(t_users.update().where(t_users.c.id == user[0]).values(
                uuid=uuid.uuid4()
            ))

    # Add all the new access control tables if they don't exist
    if not _has_table('user_case_access'):
        op.create_table('user_case_access',
                        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
                        sa.Column('case_id', sa.BigInteger(), sa.ForeignKey('cases.case_id'), nullable=False),
                        sa.Column('access_level', sa.BigInteger()),
                        keep_existing=True
                        )
        op.create_foreign_key('fk_user_case_access_user_id', 'user_case_access', 'user', ['user_id'], ['id'])
        op.create_foreign_key('fk_user_case_access_case_id', 'user_case_access', 'cases', ['case_id'], ['case_id'])
        op.create_unique_constraint('uq_user_case_access_user_id_case_id', 'user_case_access', ['user_id', 'case_id'])

    if not _has_table('user_case_effective_access'):
        op.create_table('user_case_effective_access',
                        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=False),
                        sa.Column('case_id', sa.BigInteger(), sa.ForeignKey('cases.case_id'), nullable=False),
                        sa.Column('access_level', sa.BigInteger()),
                        keep_existing=True
                        )
        op.create_foreign_key('fk_user_case_effective_access_user_id', 'user_case_effective_access',
                              'user', ['user_id'], ['id'])
        op.create_foreign_key('fk_user_case_effective_access_case_id', 'user_case_effective_access',
                              'cases', ['case_id'], ['case_id'])
        op.create_unique_constraint('uq_user_case_effective_access_user_id_case_id',
                                    'user_case_access', ['user_id', 'case_id'])

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
                        sa.Column('group_uuid', UUID(as_uuid=True), default=uuid.uuid4, nullable=False,
                                  server_default=sa.text('gen_random_uuid()'), unique=True),
                        sa.Column('group_name', sa.Text(), nullable=False),
                        sa.Column('group_description', sa.Text(), nullable=False),
                        sa.Column('group_permissions', sa.BigInteger(), nullable=False),
                        sa.Column('group_auto_follow', sa.Boolean(), nullable=False, default=False),
                        sa.Column('group_auto_follow_access_level', sa.BigInteger(), nullable=True),
                        keep_existing=True
                        )
        op.create_unique_constraint('groups_group_name_unique', 'groups', ['group_name'])

    if not _has_table('organisations'):
        op.create_table('organisations',
                        sa.Column('org_id', sa.BigInteger(), primary_key=True, nullable=False),
                        sa.Column('org_uuid', UUID(as_uuid=True), default=uuid.uuid4(), nullable=False,
                                  server_default=sa.text('gen_random_uuid()'), unique=True),
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
                        sa.Column('is_primary_org', sa.Boolean(), nullable=False),
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

    if not conn:
        conn = op.get_bind()
    # Create the groups if they don't exist
    res = conn.execute(text(f"select group_id from groups where group_name = 'Administrators';"))
    if res.rowcount == 0:
        conn.execute(text(f"insert into groups (group_name, group_description, group_permissions, group_uuid, "
                     f"group_auto_follow, group_auto_follow_access_level) "
                     f"values ('Administrators', 'Administrators', '{ac_get_mask_full_permissions()}', '{uuid.uuid4()}',"
                     f" true, 4);"))
        res = conn.execute(text(f"select group_id from groups where group_name = 'Administrators';"))
    admin_group_id = res.fetchone()[0]

    res = conn.execute(text(f"select group_id from groups where group_name = 'Analysts';"))
    if res.rowcount == 0:
        conn.execute(text(f"insert into groups (group_name, group_description, group_permissions, group_uuid, "
                     f"group_auto_follow, group_auto_follow_access_level) "
                     f"values ('Analysts', 'Standard Analysts', '{ac_get_mask_analyst()}', '{uuid.uuid4()}', true, 4);"))
        res = conn.execute(text(f"select group_id from groups where group_name = 'Analysts';"))

    analyst_group_id = res.fetchone()[0]

    # Create the organisations if they don't exist
    res = conn.execute(text(f"select org_id from organisations where org_name = 'Default Org';"))
    if res.rowcount == 0:
        conn.execute(text(f"insert into organisations (org_name, org_description, org_url, org_email, org_logo, "
                     f"org_type, org_sector, org_nationality, org_uuid) values ('Default Org', 'Default Organisation', "
                     f"'', '', "
                     f"'','', '', '', '{uuid.uuid4()}');"))
        res = conn.execute(text(f"select org_id from organisations where org_name = 'Default Org';"))
    default_org_id = res.fetchone()[0]

    # Give the organisation access to all the cases
    res = conn.execute(text(f"select case_id from cases;"))
    result_cases = [case[0] for case in res.fetchall()]
    access_level = ac_get_mask_case_access_level_full()

    # Migrate the users to the new access control system
    conn = op.get_bind()

    # Get all users with their roles
    if _has_table("user_roles"):
        res = conn.execute(text(f"select distinct roles.name, \"user\".id from user_roles INNER JOIN \"roles\" ON "
                           f"\"roles\".id = user_roles.role_id INNER JOIN \"user\" ON \"user\".id = user_roles.user_id;"))
        results_users = res.fetchall()

        for user_id in results_users:
            role_name = user_id[0]
            user_id = user_id[1]
            # Migrate user to groups
            if role_name == 'administrator':
                conn.execute(text(f"insert into user_group (user_id, group_id) values ({user_id}, {admin_group_id}) "
                             f"on conflict do nothing;"))

            elif role_name == 'investigator':
                conn.execute(text(f"insert into user_group (user_id, group_id) values ({user_id}, {analyst_group_id}) "
                             f"on conflict do nothing;"))

            # Add user to default organisation
            conn.execute(text(f"insert into user_organisation (user_id, org_id, is_primary_org) values ({user_id}, "
                         f"{default_org_id}, true) on conflict do nothing;"))

            # Add default cases effective permissions
            for case_id in result_cases:
                conn.execute(text(f"insert into user_case_effective_access (case_id, user_id, access_level) values "
                             f"({case_id}, {user_id}, {access_level}) on conflict do nothing;"))

        op.drop_table('user_roles')

    pass


def downgrade():
    pass
