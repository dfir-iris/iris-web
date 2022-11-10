"""Objects UUID field

Revision ID: 20447ecb2245
Revises: ad4e0cd17597
Create Date: 2022-09-23 21:07:20.007874

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID

from app.alembic.alembic_utils import _table_has_column

revision = '20447ecb2245'
down_revision = 'ad4e0cd17597'
branch_labels = None
depends_on = None


def upgrade():
    # ---- Cases ----
    op.alter_column('cases', 'case_id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    if not _table_has_column('cases', 'case_uuid'):
        op.add_column('cases',
                      sa.Column('case_uuid', UUID(as_uuid=True), server_default=text("gen_random_uuid()"),
                                nullable=False)
                      )
    # ---- Events ----
    op.alter_column('cases_events', 'event_id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    if not _table_has_column('cases_events', 'event_uuid'):
        op.add_column('cases_events',
                      sa.Column('event_uuid', UUID(as_uuid=True), server_default=text("gen_random_uuid()"),
                                nullable=False)
                      )
    # ---- Clients ----
    op.alter_column('client', 'client_id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    if not _table_has_column('client', 'client_uuid'):
        op.add_column('client',
                      sa.Column('client_uuid', UUID(as_uuid=True), server_default=text("gen_random_uuid()"),
                                nullable=False)
                      )

    # ---- Case assets ----
    op.alter_column('case_assets', 'asset_id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    if not _table_has_column('case_assets', 'asset_uuid'):
        op.add_column('case_assets',
                      sa.Column('asset_uuid', UUID(as_uuid=True), server_default=text("gen_random_uuid()"),
                                nullable=False)
                      )

    # ---- Case objects states ----
    op.alter_column('object_state', 'object_id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    # ---- Case event IOC ----
    op.alter_column('case_events_ioc', 'id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    # ---- Case event assets ----
    op.alter_column('case_events_assets', 'id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    # ---- IOC ----
    op.alter_column('ioc', 'ioc_id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    if not _table_has_column('ioc', 'ioc_uuid'):
        op.add_column('ioc',
                      sa.Column('ioc_uuid', UUID(as_uuid=True), server_default=text("gen_random_uuid()"),
                                nullable=False)
                      )

    # ---- Notes ----
    op.alter_column('notes', 'note_id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    if not _table_has_column('notes', 'note_uuid'):
        op.add_column('notes',
                      sa.Column('note_uuid', UUID(as_uuid=True), server_default=text("gen_random_uuid()"),
                                nullable=False)
                      )

    # ---- Notes group ----
    op.alter_column('notes_group', 'group_id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    if not _table_has_column('notes_group', 'group_uuid'):
        op.add_column('notes_group',
                      sa.Column('group_uuid', UUID(as_uuid=True), server_default=text("gen_random_uuid()"),
                                nullable=False)
                      )

    # ---- Notes group link ----
    op.alter_column('notes_group_link', 'link_id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    # ---- case received files ----
    op.alter_column('case_received_file', 'id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    if not _table_has_column('case_received_file', 'file_uuid'):
        op.add_column('case_received_file',
                      sa.Column('file_uuid', UUID(as_uuid=True), server_default=text("gen_random_uuid()"),
                                nullable=False)
                      )

    # ---- case tasks ----
    op.alter_column('case_tasks', 'id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    if not _table_has_column('case_tasks', 'task_uuid'):
        op.add_column('case_tasks',
                      sa.Column('task_uuid', UUID(as_uuid=True), server_default=text("gen_random_uuid()"),
                                nullable=False)
                      )

    # ---- global tasks ----
    op.alter_column('global_tasks', 'id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    if not _table_has_column('global_tasks', 'task_uuid'):
        op.add_column('global_tasks',
                      sa.Column('task_uuid', UUID(as_uuid=True), server_default=text("gen_random_uuid()"),
                                nullable=False)
                      )

    # ---- user activity ----
    op.alter_column('user_activity', 'id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    # ---- Iris Hooks ----
    op.alter_column('iris_module_hooks', 'id',
                    existing_type=sa.INTEGER(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    pass


def downgrade():
    pass
