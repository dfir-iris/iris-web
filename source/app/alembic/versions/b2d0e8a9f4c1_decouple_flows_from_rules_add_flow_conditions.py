"""Decouple investigation flows from incident rules.

Flows now own their own matching conditions and can attach to alerts
and/or incidents on their own — the `attach_flow` rule action is
retired (rules only stack alerts into incidents). This migration adds:

  * `investigation_flows.flow_target`     — 'alert' / 'incident' / 'both'
  * `investigation_flows.flow_conditions` — JSONB, same DSL as rules
  * `investigation_flows.flow_priority`   — tie-breaker
  * `incidents.incident_investigation_flow_id` — cached FK
  * `incident_investigation_progress`     — per-incident check-off table

Every step is guarded by `_has_table`/`_table_has_column` so the
migration is idempotent — safe to re-run.

Revision ID: b2d0e8a9f4c1
Revises: a1c9f7b2e3d4
Create Date: 2026-07-02 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _has_table
from app.alembic.alembic_utils import _table_has_column


revision = 'b2d0e8a9f4c1'
down_revision = 'a1c9f7b2e3d4'
branch_labels = None
depends_on = None


def _add_flow_columns():
    if not _table_has_column('investigation_flows', 'flow_target'):
        op.add_column(
            'investigation_flows',
            sa.Column('flow_target', sa.Text(), nullable=False,
                      server_default=sa.text("'alert'")),
        )
    if not _table_has_column('investigation_flows', 'flow_conditions'):
        op.add_column(
            'investigation_flows',
            sa.Column(
                'flow_conditions', sa.dialects.postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{\"logic\":\"and\",\"conditions\":[]}'::jsonb"),
            ),
        )
    if not _table_has_column('investigation_flows', 'flow_priority'):
        op.add_column(
            'investigation_flows',
            sa.Column('flow_priority', sa.Integer(), nullable=False,
                      server_default=sa.text('100')),
        )


def _add_incident_flow_column():
    if _table_has_column('incidents', 'incident_investigation_flow_id'):
        return
    op.add_column(
        'incidents',
        sa.Column('incident_investigation_flow_id', sa.BigInteger(),
                  sa.ForeignKey('investigation_flows.flow_id'), nullable=True),
    )


def _create_incident_investigation_progress():
    if _has_table('incident_investigation_progress'):
        return
    op.create_table(
        'incident_investigation_progress',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('incident_id', sa.BigInteger(),
                  sa.ForeignKey('incidents.incident_id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('step_id', sa.BigInteger(),
                  sa.ForeignKey('investigation_flow_steps.step_id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('completed_by_user_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('note', sa.Text(), nullable=True),
        sa.UniqueConstraint('incident_id', 'step_id',
                            name='uq_incident_investigation_progress_incident_step'),
    )


def upgrade():
    _add_flow_columns()
    _add_incident_flow_column()
    _create_incident_investigation_progress()


def downgrade():
    op.drop_table('incident_investigation_progress')
    if _table_has_column('incidents', 'incident_investigation_flow_id'):
        op.drop_column('incidents', 'incident_investigation_flow_id')
    if _table_has_column('investigation_flows', 'flow_priority'):
        op.drop_column('investigation_flows', 'flow_priority')
    if _table_has_column('investigation_flows', 'flow_conditions'):
        op.drop_column('investigation_flows', 'flow_conditions')
    if _table_has_column('investigation_flows', 'flow_target'):
        op.drop_column('investigation_flows', 'flow_target')
