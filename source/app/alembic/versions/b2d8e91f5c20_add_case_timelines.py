"""Add named timelines per case + event<->timeline junction.

Introduces `case_timelines` and `case_event_timelines` so a single
case can host multiple named timelines (e.g. "Attacker activity",
"Network", "Forensic") and the same event can appear on more than
one. The SPA's timeline view will render a multi-select sidebar over
these.

Backfill: for each existing case, create a single "Main" timeline
(is_default=True) and attach every existing event to it. After this
migration the user-visible behaviour is unchanged — all events stay
on one timeline labeled "Main" — but the data model is in place for
the SPA to expose the multi-timeline UX.

Revision ID: b2d8e91f5c20
Revises: a1c7d92f4b10
Create Date: 2026-06-27 09:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _has_table


revision = 'b2d8e91f5c20'
down_revision = 'a1c7d92f4b10'
branch_labels = None
depends_on = None


def upgrade():
    if not _has_table('case_timelines'):
        op.create_table(
            'case_timelines',
            sa.Column('timeline_id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('case_id', sa.BigInteger(), nullable=False),
            sa.Column('name', sa.String(length=128), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('color', sa.String(length=7), nullable=True),
            sa.Column('is_default', sa.Boolean(), nullable=False,
                      server_default=sa.text('false')),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('now()')),
            sa.Column('created_by_id', sa.BigInteger(), nullable=True),
            sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['created_by_id'], ['user.id']),
            sa.PrimaryKeyConstraint('timeline_id'),
            sa.UniqueConstraint('case_id', 'name', name='uq_case_timelines_case_name'),
        )
        op.create_index('ix_case_timelines_case_id', 'case_timelines', ['case_id'])

    if not _has_table('case_event_timelines'):
        op.create_table(
            'case_event_timelines',
            sa.Column('event_id', sa.BigInteger(), nullable=False),
            sa.Column('timeline_id', sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(['event_id'], ['cases_events.event_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['timeline_id'], ['case_timelines.timeline_id'],
                                    ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('event_id', 'timeline_id'),
        )
        op.create_index('ix_case_event_timelines_timeline_id',
                        'case_event_timelines', ['timeline_id'])

    # Backfill: one "Main" timeline per existing case, all current
    # events linked to it. We run this as raw SQL so it works on
    # databases that already have user data — no per-row Python loop.
    bind = op.get_bind()
    bind.execute(sa.text(
        """
        INSERT INTO case_timelines (case_id, name, is_default)
        SELECT c.case_id, 'Main', true
        FROM cases c
        WHERE NOT EXISTS (
            SELECT 1 FROM case_timelines t
            WHERE t.case_id = c.case_id AND t.is_default = true
        )
        """
    ))
    bind.execute(sa.text(
        """
        INSERT INTO case_event_timelines (event_id, timeline_id)
        SELECT e.event_id, t.timeline_id
        FROM cases_events e
        JOIN case_timelines t ON t.case_id = e.case_id AND t.is_default = true
        WHERE NOT EXISTS (
            SELECT 1 FROM case_event_timelines x
            WHERE x.event_id = e.event_id AND x.timeline_id = t.timeline_id
        )
        """
    ))


def downgrade():
    if _has_table('case_event_timelines'):
        op.drop_index('ix_case_event_timelines_timeline_id',
                      table_name='case_event_timelines')
        op.drop_table('case_event_timelines')
    if _has_table('case_timelines'):
        op.drop_index('ix_case_timelines_case_id', table_name='case_timelines')
        op.drop_table('case_timelines')
