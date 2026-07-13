"""Re-run the event<->default-timeline backfill.

The previous migration (`b2d8e91f5c20_add_case_timelines`) shipped the
backfill SQL alongside the schema change, but a class of dev / staging
environments ended up with the schema applied while leaving the
backfill rows missing — either because the migration was run on a
partial intermediate revision of this branch, or because new events
created via the legacy `/case/timeline/events/...` endpoint (which
predate the timeline-aware event handlers) landed without an entry in
`case_event_timelines`.

This migration is a safety net: for every case that has a default
timeline AND events that are not yet linked to ANY timeline, it
attaches those events to the default. Idempotent — if everything is
already wired, it inserts nothing.

Revision ID: c3e9fa0e6d31
Revises: b2d8e91f5c20
Create Date: 2026-06-27 10:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'c3e9fa0e6d31'
down_revision = 'b2d8e91f5c20'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # First make sure every case has a Main default timeline. This
    # duplicates the previous migration's guarantee but costs nothing
    # when the row already exists.
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

    # Attach every event that lives on no timeline at all to its case's
    # default timeline. The `NOT EXISTS` against any timeline membership
    # (not just the default) means events the user explicitly removed
    # from every timeline get re-attached — but the "no timelines" state
    # only happens when the row was never backfilled in the first place,
    # so this is safe.
    bind.execute(sa.text(
        """
        INSERT INTO case_event_timelines (event_id, timeline_id)
        SELECT e.event_id, t.timeline_id
        FROM cases_events e
        JOIN case_timelines t ON t.case_id = e.case_id AND t.is_default = true
        WHERE NOT EXISTS (
            SELECT 1 FROM case_event_timelines x
            WHERE x.event_id = e.event_id
        )
        """
    ))


def downgrade():
    # Backfill is data-only — no schema to revert. A downgrade is a
    # no-op rather than blowing away user data that may include
    # legitimate explicit attachments made after the upgrade.
    pass
