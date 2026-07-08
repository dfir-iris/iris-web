"""Add war-room note folders and revisions.

Mirrors the case-notes folder + revision tables onto war rooms so the
war-room notes tab can render the same directory tree + versioning
UI. Two new tables plus a nullable `folder_id` column on the existing
`war_room_note` table.

  * `war_room_note_folder`   — self-referencing adjacency-list tree,
                                scoped to a war room; cascade delete
                                on both `war_room_id` and `parent_id`.
  * `war_room_note.folder_id` — nullable FK; root-level notes are `NULL`.
                                No cascade — folder deletion walks the
                                subtree in the business layer so revision
                                history is torn down alongside each note.
  * `war_room_note_revision` — immutable per-note history, cascade delete
                                on `note_id`.

Every step is guarded by `_has_table` / `_table_has_column` so the
migration is idempotent — safe to re-run on partially-upgraded
environments.

Revision ID: d9f4a2c8b103
Revises: f3a1b2c3d4e5
Create Date: 2026-07-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _has_table
from app.alembic.alembic_utils import _table_has_column


revision = 'd9f4a2c8b103'
down_revision = 'f3a1b2c3d4e5'
branch_labels = None
depends_on = None


def _create_war_room_note_folder():
    if _has_table('war_room_note_folder'):
        return
    op.create_table(
        'war_room_note_folder',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('war_room_id', sa.BigInteger(),
                  sa.ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('parent_id', sa.BigInteger(),
                  sa.ForeignKey('war_room_note_folder.id', ondelete='CASCADE'),
                  nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
    )


def _add_note_folder_column():
    if _table_has_column('war_room_note', 'folder_id'):
        return
    op.add_column(
        'war_room_note',
        sa.Column('folder_id', sa.BigInteger(),
                  sa.ForeignKey('war_room_note_folder.id'), nullable=True),
    )


def _create_war_room_note_revision():
    if _has_table('war_room_note_revision'):
        return
    op.create_table(
        'war_room_note_revision',
        sa.Column('revision_id', sa.BigInteger(), primary_key=True),
        sa.Column('note_id', sa.BigInteger(),
                  sa.ForeignKey('war_room_note.note_id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('revised_by_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.Column('revised_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
    )


def upgrade():
    _create_war_room_note_folder()
    _add_note_folder_column()
    _create_war_room_note_revision()


def downgrade():
    op.drop_table('war_room_note_revision')
    if _table_has_column('war_room_note', 'folder_id'):
        op.drop_column('war_room_note', 'folder_id')
    op.drop_table('war_room_note_folder')
