"""Add the war rooms feature.

Creates every table behind the war-room workspace:

  * `war_room` — top-level workspace row
  * `war_room_case` — N:N to attached cases
  * `war_room_member` — roster
  * `war_room_timeline` / `war_room_timeline_event` — per-war-room timelines
  * `war_room_chat_message` / `war_room_chat_reaction` — chat stream
  * `war_room_task` — war-room-level tasks
  * `war_room_note` — sticky notes / collab markdown
  * `war_room_sitrep` — versioned situational reports
  * `war_room_graph_node` / `war_room_graph_edge` — cases-as-graph board
  * `war_room_datastore_file` — files attached directly to the war room
  * `user_war_room_access`, `group_war_room_access`,
    `user_war_room_effective_access` — ACL precedence chain

Every step is guarded by `_has_table`/`_table_has_column`/`index_exists`
so the migration is idempotent on any existing IRIS deployment — older
versions, partial-upgrade environments, and re-runs after a failed
attempt all converge on the same schema without raising on existing
objects.

Three new permission flags (`war_rooms_read`/_write/_create) are
defined as enum values rather than DB rows, so no permission table
seeding is needed — the bitmask values land on `Group.group_permissions`
the first time an admin toggles them on.

Revision ID: d4f0a23c8e51
Revises: c3e9fa0e6d31
Create Date: 2026-06-27 11:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _has_table
from app.alembic.alembic_utils import index_exists


revision = 'd4f0a23c8e51'
down_revision = 'c3e9fa0e6d31'
branch_labels = None
depends_on = None


def _create_war_room():
    if _has_table('war_room'):
        return
    op.create_table(
        'war_room',
        sa.Column('war_room_id', sa.BigInteger(), primary_key=True),
        sa.Column('war_room_uuid', sa.dialects.postgresql.UUID(as_uuid=True),
                  nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(256), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('state', sa.String(16), nullable=False,
                  server_default=sa.text("'open'")),
        sa.Column('severity_id', sa.BigInteger(),
                  sa.ForeignKey('severities.severity_id'), nullable=True),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('created_by_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('closed_by_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.Column('custom_attributes', sa.dialects.postgresql.JSONB(),
                  nullable=True),
        sa.UniqueConstraint('war_room_uuid', name='uq_war_room_uuid'),
    )


def _create_war_room_case():
    if _has_table('war_room_case'):
        return
    op.create_table(
        'war_room_case',
        sa.Column('war_room_id', sa.BigInteger(), nullable=False),
        sa.Column('case_id', sa.BigInteger(), nullable=False),
        sa.Column('attached_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('attached_by_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['war_room_id'], ['war_room.war_room_id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('war_room_id', 'case_id'),
        sa.UniqueConstraint('war_room_id', 'case_id', name='uq_war_room_case'),
    )
    if not index_exists('war_room_case', 'ix_war_room_case_case_id'):
        op.create_index('ix_war_room_case_case_id', 'war_room_case', ['case_id'])


def _create_war_room_member():
    if _has_table('war_room_member'):
        return
    op.create_table(
        'war_room_member',
        sa.Column('war_room_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.String(16), nullable=False,
                  server_default=sa.text("'responder'")),
        sa.Column('added_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('added_by_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.ForeignKeyConstraint(['war_room_id'], ['war_room.war_room_id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('war_room_id', 'user_id'),
        sa.UniqueConstraint('war_room_id', 'user_id', name='uq_war_room_member'),
    )


def _create_war_room_timelines():
    if not _has_table('war_room_timeline'):
        op.create_table(
            'war_room_timeline',
            sa.Column('timeline_id', sa.BigInteger(), primary_key=True),
            sa.Column('war_room_id', sa.BigInteger(), nullable=False),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('color', sa.String(7), nullable=True),
            sa.Column('is_default', sa.Boolean(), nullable=False,
                      server_default=sa.text('false')),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('now()')),
            sa.Column('created_by_id', sa.BigInteger(),
                      sa.ForeignKey('user.id'), nullable=True),
            sa.ForeignKeyConstraint(['war_room_id'], ['war_room.war_room_id'],
                                    ondelete='CASCADE'),
            sa.UniqueConstraint('war_room_id', 'name',
                                name='uq_war_room_timeline_name'),
        )
        if not index_exists('war_room_timeline', 'ix_war_room_timeline_war_room_id'):
            op.create_index('ix_war_room_timeline_war_room_id',
                            'war_room_timeline', ['war_room_id'])

    if not _has_table('war_room_timeline_event'):
        op.create_table(
            'war_room_timeline_event',
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('timeline_id', sa.BigInteger(), nullable=False),
            sa.Column('case_id', sa.BigInteger(), nullable=True),
            sa.Column('event_id', sa.BigInteger(), nullable=True),
            sa.Column('title', sa.Text(), nullable=True),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('event_date', sa.DateTime(), nullable=True),
            sa.Column('event_tz', sa.String(16), nullable=True),
            sa.Column('color', sa.String(7), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('now()')),
            sa.Column('created_by_id', sa.BigInteger(),
                      sa.ForeignKey('user.id'), nullable=True),
            sa.ForeignKeyConstraint(['timeline_id'],
                                    ['war_room_timeline.timeline_id'],
                                    ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'],
                                    ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['event_id'], ['cases_events.event_id'],
                                    ondelete='CASCADE'),
            sa.CheckConstraint(
                "(case_id IS NULL AND event_id IS NULL) OR "
                "(case_id IS NOT NULL AND event_id IS NOT NULL)",
                name='ck_war_room_timeline_event_case_event_pair'
            ),
        )
        if not index_exists('war_room_timeline_event',
                            'ix_war_room_timeline_event_timeline_id'):
            op.create_index('ix_war_room_timeline_event_timeline_id',
                            'war_room_timeline_event', ['timeline_id'])


def _create_war_room_chat():
    if not _has_table('war_room_chat_message'):
        op.create_table(
            'war_room_chat_message',
            sa.Column('message_id', sa.BigInteger(), primary_key=True),
            sa.Column('war_room_id', sa.BigInteger(), nullable=False),
            sa.Column('author_id', sa.BigInteger(),
                      sa.ForeignKey('user.id'), nullable=True),
            sa.Column('body', sa.Text(), nullable=True),
            sa.Column('kind', sa.String(32), nullable=False,
                      server_default=sa.text("'message'")),
            sa.Column('ref_type', sa.String(32), nullable=True),
            sa.Column('ref_id', sa.BigInteger(), nullable=True),
            sa.Column('ref_case_id', sa.BigInteger(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('now()')),
            sa.Column('edited_at', sa.DateTime(), nullable=True),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['war_room_id'], ['war_room.war_room_id'],
                                    ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['ref_case_id'], ['cases.case_id'],
                                    ondelete='SET NULL'),
        )
        for idx, cols in (
            ('ix_war_room_chat_message_war_room_id', ['war_room_id']),
            ('ix_war_room_chat_message_war_room_id_created_at',
             ['war_room_id', 'created_at']),
            ('ix_war_room_chat_message_ref_case_id', ['ref_case_id']),
        ):
            if not index_exists('war_room_chat_message', idx):
                op.create_index(idx, 'war_room_chat_message', cols)

    if not _has_table('war_room_chat_reaction'):
        op.create_table(
            'war_room_chat_reaction',
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('message_id', sa.BigInteger(), nullable=False),
            sa.Column('user_id', sa.BigInteger(), nullable=False),
            sa.Column('emoji', sa.String(32), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('now()')),
            sa.ForeignKeyConstraint(['message_id'],
                                    ['war_room_chat_message.message_id'],
                                    ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
            sa.UniqueConstraint('message_id', 'user_id', 'emoji',
                                name='uq_war_room_chat_reaction'),
        )
        if not index_exists('war_room_chat_reaction',
                            'ix_war_room_chat_reaction_message_id'):
            op.create_index('ix_war_room_chat_reaction_message_id',
                            'war_room_chat_reaction', ['message_id'])


def _create_war_room_tasks():
    if _has_table('war_room_task'):
        return
    op.create_table(
        'war_room_task',
        sa.Column('task_id', sa.BigInteger(), primary_key=True),
        sa.Column('war_room_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status_id', sa.Integer(),
                  sa.ForeignKey('task_status.id'), nullable=True),
        sa.Column('assignee_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.Column('due_at', sa.DateTime(), nullable=True),
        sa.Column('source_case_id', sa.BigInteger(), nullable=True),
        sa.Column('source_case_task_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('created_by_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('closed_by_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('custom_attributes', sa.dialects.postgresql.JSONB(),
                  nullable=True),
        sa.ForeignKeyConstraint(['war_room_id'], ['war_room.war_room_id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_case_id'], ['cases.case_id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_case_task_id'], ['case_tasks.id'],
                                ondelete='SET NULL'),
    )
    if not index_exists('war_room_task', 'ix_war_room_task_war_room_id'):
        op.create_index('ix_war_room_task_war_room_id',
                        'war_room_task', ['war_room_id'])


def _create_war_room_note():
    if _has_table('war_room_note'):
        return
    op.create_table(
        'war_room_note',
        sa.Column('note_id', sa.BigInteger(), primary_key=True),
        sa.Column('war_room_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('created_by_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.Column('updated_by_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.ForeignKeyConstraint(['war_room_id'], ['war_room.war_room_id'],
                                ondelete='CASCADE'),
    )
    if not index_exists('war_room_note', 'ix_war_room_note_war_room_id'):
        op.create_index('ix_war_room_note_war_room_id',
                        'war_room_note', ['war_room_id'])


def _create_war_room_sitrep():
    if _has_table('war_room_sitrep'):
        return
    op.create_table(
        'war_room_sitrep',
        sa.Column('sitrep_id', sa.BigInteger(), primary_key=True),
        sa.Column('war_room_id', sa.BigInteger(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('body_md', sa.Text(), nullable=False),
        sa.Column('snapshot_json', sa.dialects.postgresql.JSONB(),
                  nullable=True),
        sa.Column('authored_by_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.Column('authored_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('published', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['war_room_id'], ['war_room.war_room_id'],
                                ondelete='CASCADE'),
        sa.UniqueConstraint('war_room_id', 'version',
                            name='uq_war_room_sitrep_version'),
    )
    if not index_exists('war_room_sitrep', 'ix_war_room_sitrep_war_room_id'):
        op.create_index('ix_war_room_sitrep_war_room_id',
                        'war_room_sitrep', ['war_room_id'])


def _create_war_room_graph():
    if not _has_table('war_room_graph_node'):
        op.create_table(
            'war_room_graph_node',
            sa.Column('node_id', sa.BigInteger(), primary_key=True),
            sa.Column('war_room_id', sa.BigInteger(), nullable=False),
            sa.Column('kind', sa.String(16), nullable=False),
            sa.Column('ref_id', sa.BigInteger(), nullable=True),
            sa.Column('label', sa.Text(), nullable=True),
            sa.Column('note_md', sa.Text(), nullable=True),
            sa.Column('color', sa.String(7), nullable=True),
            sa.Column('x', sa.Float(), nullable=False, server_default=sa.text('0')),
            sa.Column('y', sa.Float(), nullable=False, server_default=sa.text('0')),
            sa.ForeignKeyConstraint(['war_room_id'], ['war_room.war_room_id'],
                                    ondelete='CASCADE'),
        )
        if not index_exists('war_room_graph_node',
                            'ix_war_room_graph_node_war_room_id'):
            op.create_index('ix_war_room_graph_node_war_room_id',
                            'war_room_graph_node', ['war_room_id'])

    if not _has_table('war_room_graph_edge'):
        op.create_table(
            'war_room_graph_edge',
            sa.Column('edge_id', sa.BigInteger(), primary_key=True),
            sa.Column('war_room_id', sa.BigInteger(), nullable=False),
            sa.Column('from_node_id', sa.BigInteger(), nullable=False),
            sa.Column('to_node_id', sa.BigInteger(), nullable=False),
            sa.Column('label', sa.Text(), nullable=True),
            sa.Column('note_md', sa.Text(), nullable=True),
            sa.Column('style', sa.String(16), nullable=True),
            sa.ForeignKeyConstraint(['war_room_id'], ['war_room.war_room_id'],
                                    ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['from_node_id'],
                                    ['war_room_graph_node.node_id'],
                                    ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['to_node_id'],
                                    ['war_room_graph_node.node_id'],
                                    ondelete='CASCADE'),
        )
        if not index_exists('war_room_graph_edge',
                            'ix_war_room_graph_edge_war_room_id'):
            op.create_index('ix_war_room_graph_edge_war_room_id',
                            'war_room_graph_edge', ['war_room_id'])


def _create_war_room_datastore():
    if _has_table('war_room_datastore_file'):
        return
    op.create_table(
        'war_room_datastore_file',
        sa.Column('file_id', sa.BigInteger(), primary_key=True),
        sa.Column('war_room_id', sa.BigInteger(), nullable=False),
        sa.Column('filename', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(128), nullable=True),
        sa.Column('sha256', sa.String(64), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('uploaded_by_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['war_room_id'], ['war_room.war_room_id'],
                                ondelete='CASCADE'),
    )
    if not index_exists('war_room_datastore_file',
                        'ix_war_room_datastore_file_war_room_id'):
        op.create_index('ix_war_room_datastore_file_war_room_id',
                        'war_room_datastore_file', ['war_room_id'])


def _create_war_room_acl():
    if not _has_table('user_war_room_access'):
        op.create_table(
            'user_war_room_access',
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('user_id', sa.BigInteger(), nullable=False),
            sa.Column('war_room_id', sa.BigInteger(), nullable=False),
            sa.Column('access_level', sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['war_room_id'], ['war_room.war_room_id'],
                                    ondelete='CASCADE'),
            sa.UniqueConstraint('war_room_id', 'user_id',
                                name='uq_user_war_room_access_room_user'),
        )

    if not _has_table('group_war_room_access'):
        op.create_table(
            'group_war_room_access',
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('group_id', sa.BigInteger(), nullable=False),
            sa.Column('war_room_id', sa.BigInteger(), nullable=False),
            sa.Column('access_level', sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(['group_id'], ['groups.group_id'],
                                    ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['war_room_id'], ['war_room.war_room_id'],
                                    ondelete='CASCADE'),
            sa.UniqueConstraint('war_room_id', 'group_id',
                                name='uq_group_war_room_access_room_group'),
        )

    if not _has_table('user_war_room_effective_access'):
        op.create_table(
            'user_war_room_effective_access',
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('user_id', sa.BigInteger(), nullable=False),
            sa.Column('war_room_id', sa.BigInteger(), nullable=False),
            sa.Column('access_level', sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['war_room_id'], ['war_room.war_room_id'],
                                    ondelete='CASCADE'),
            sa.UniqueConstraint('war_room_id', 'user_id',
                                name='uq_user_war_room_effective_access_room_user'),
        )
        if not index_exists('user_war_room_effective_access',
                            'ix_user_war_room_effective_access_user_id'):
            op.create_index('ix_user_war_room_effective_access_user_id',
                            'user_war_room_effective_access', ['user_id'])


def upgrade():
    _create_war_room()
    _create_war_room_case()
    _create_war_room_member()
    _create_war_room_timelines()
    _create_war_room_chat()
    _create_war_room_tasks()
    _create_war_room_note()
    _create_war_room_sitrep()
    _create_war_room_graph()
    _create_war_room_datastore()
    _create_war_room_acl()


def downgrade():
    # Drop in reverse dependency order. Each step is guarded so a
    # partial downgrade re-run on a partial schema doesn't blow up.
    for table in (
        'user_war_room_effective_access',
        'group_war_room_access',
        'user_war_room_access',
        'war_room_datastore_file',
        'war_room_graph_edge',
        'war_room_graph_node',
        'war_room_sitrep',
        'war_room_note',
        'war_room_task',
        'war_room_chat_reaction',
        'war_room_chat_message',
        'war_room_timeline_event',
        'war_room_timeline',
        'war_room_member',
        'war_room_case',
        'war_room',
    ):
        if _has_table(table):
            op.drop_table(table)
