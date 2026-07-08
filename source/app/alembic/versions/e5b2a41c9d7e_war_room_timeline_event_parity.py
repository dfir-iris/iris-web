"""War-room timeline event: parity with case events.

Extends `war_room_timeline_event` with the columns case events already
carry, plus the M2M join tables for assets and IOCs. After this
migration the two event shapes are near-siblings — the frontend event
card component ports cleanly from case-timeline to war-room-timeline
with only field-name adaptations.

  * `war_room_timeline_event.uuid`, `parent_id`, `source`, `raw`,
    `tags`, `is_flagged`, `modification_history`
  * `war_room_timeline_event_assets` — M2M to `case_assets`
  * `war_room_timeline_event_iocs` — M2M to `ioc`

Per-event comments are intentionally out of scope; war-room chat is the
conversation surface for a war room, not per-event threads.

Every step is guarded by `_has_table` / `_table_has_column` so the
migration is idempotent — safe to re-run on partially-upgraded
environments.

Revision ID: e5b2a41c9d7e
Revises: d9f4a2c8b103
Create Date: 2026-07-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _has_table
from app.alembic.alembic_utils import _table_has_column


revision = 'e5b2a41c9d7e'
down_revision = 'd9f4a2c8b103'
branch_labels = None
depends_on = None


def _add_columns():
    # Individual `_table_has_column` guards keep the migration
    # replayable — production runs where an earlier attempt bailed
    # partway through won't re-add a column that's already there.
    if not _table_has_column('war_room_timeline_event', 'uuid'):
        op.add_column(
            'war_room_timeline_event',
            sa.Column('uuid', sa.dialects.postgresql.UUID(as_uuid=True),
                      nullable=False,
                      server_default=sa.text('gen_random_uuid()')),
        )
        op.create_unique_constraint(
            'uq_war_room_timeline_event_uuid',
            'war_room_timeline_event', ['uuid'],
        )
    if not _table_has_column('war_room_timeline_event', 'parent_id'):
        op.add_column(
            'war_room_timeline_event',
            sa.Column('parent_id', sa.BigInteger(), nullable=True),
        )
        op.create_foreign_key(
            'fk_war_room_timeline_event_parent',
            'war_room_timeline_event', 'war_room_timeline_event',
            ['parent_id'], ['id'], ondelete='SET NULL',
        )
    if not _table_has_column('war_room_timeline_event', 'source'):
        op.add_column(
            'war_room_timeline_event',
            sa.Column('source', sa.Text(), nullable=True),
        )
    if not _table_has_column('war_room_timeline_event', 'raw'):
        op.add_column(
            'war_room_timeline_event',
            sa.Column('raw', sa.Text(), nullable=True),
        )
    if not _table_has_column('war_room_timeline_event', 'tags'):
        op.add_column(
            'war_room_timeline_event',
            sa.Column('tags', sa.Text(), nullable=True),
        )
    if not _table_has_column('war_room_timeline_event', 'is_flagged'):
        op.add_column(
            'war_room_timeline_event',
            sa.Column('is_flagged', sa.Boolean(), nullable=False,
                      server_default=sa.text('false')),
        )
    if not _table_has_column('war_room_timeline_event',
                             'modification_history'):
        op.add_column(
            'war_room_timeline_event',
            sa.Column('modification_history',
                      sa.dialects.postgresql.JSONB(), nullable=True),
        )


def _create_war_room_timeline_event_assets():
    if _has_table('war_room_timeline_event_assets'):
        return
    op.create_table(
        'war_room_timeline_event_assets',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('event_id', sa.BigInteger(),
                  sa.ForeignKey('war_room_timeline_event.id',
                                ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('asset_id', sa.BigInteger(),
                  sa.ForeignKey('case_assets.asset_id',
                                ondelete='CASCADE'),
                  nullable=False),
        sa.UniqueConstraint('event_id', 'asset_id',
                            name='uq_war_room_timeline_event_asset'),
    )


def _create_war_room_timeline_event_iocs():
    if _has_table('war_room_timeline_event_iocs'):
        return
    op.create_table(
        'war_room_timeline_event_iocs',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('event_id', sa.BigInteger(),
                  sa.ForeignKey('war_room_timeline_event.id',
                                ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('ioc_id', sa.BigInteger(),
                  sa.ForeignKey('ioc.ioc_id', ondelete='CASCADE'),
                  nullable=False),
        sa.UniqueConstraint('event_id', 'ioc_id',
                            name='uq_war_room_timeline_event_ioc'),
    )


def upgrade():
    _add_columns()
    _create_war_room_timeline_event_assets()
    _create_war_room_timeline_event_iocs()


def downgrade():
    op.drop_table('war_room_timeline_event_iocs')
    op.drop_table('war_room_timeline_event_assets')
    if _table_has_column('war_room_timeline_event', 'modification_history'):
        op.drop_column('war_room_timeline_event', 'modification_history')
    if _table_has_column('war_room_timeline_event', 'is_flagged'):
        op.drop_column('war_room_timeline_event', 'is_flagged')
    if _table_has_column('war_room_timeline_event', 'tags'):
        op.drop_column('war_room_timeline_event', 'tags')
    if _table_has_column('war_room_timeline_event', 'raw'):
        op.drop_column('war_room_timeline_event', 'raw')
    if _table_has_column('war_room_timeline_event', 'source'):
        op.drop_column('war_room_timeline_event', 'source')
    if _table_has_column('war_room_timeline_event', 'parent_id'):
        op.drop_constraint('fk_war_room_timeline_event_parent',
                           'war_room_timeline_event', type_='foreignkey')
        op.drop_column('war_room_timeline_event', 'parent_id')
    if _table_has_column('war_room_timeline_event', 'uuid'):
        op.drop_constraint('uq_war_room_timeline_event_uuid',
                           'war_room_timeline_event', type_='unique')
        op.drop_column('war_room_timeline_event', 'uuid')
