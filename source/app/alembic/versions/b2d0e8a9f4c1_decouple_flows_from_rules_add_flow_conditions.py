"""Decouple investigation flows from cluster rules.

Flows now own their own matching conditions and can attach to alerts
and/or alert clusters on their own — the `attach_flow` rule action is
retired (rules only stack alerts into clusters). This migration adds:

  * `investigation_flows.flow_target`     — 'alert' / 'alert_cluster' / 'both'
  * `investigation_flows.flow_conditions` — JSONB, same DSL as rules
  * `investigation_flows.flow_priority`   — tie-breaker
  * `alert_clusters.cluster_investigation_flow_id` — cached FK
  * `alert_cluster_investigation_progress`         — per-cluster check-off table

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


def _add_cluster_flow_column():
    if _table_has_column('alert_clusters', 'cluster_investigation_flow_id'):
        return
    op.add_column(
        'alert_clusters',
        sa.Column('cluster_investigation_flow_id', sa.BigInteger(),
                  sa.ForeignKey('investigation_flows.flow_id'), nullable=True),
    )


def _create_alert_cluster_investigation_progress():
    if _has_table('alert_cluster_investigation_progress'):
        return
    op.create_table(
        'alert_cluster_investigation_progress',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('cluster_id', sa.BigInteger(),
                  sa.ForeignKey('alert_clusters.cluster_id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('step_id', sa.BigInteger(),
                  sa.ForeignKey('investigation_flow_steps.step_id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('completed_by_user_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('note', sa.Text(), nullable=True),
        sa.UniqueConstraint('cluster_id', 'step_id',
                            name='uq_alert_cluster_investigation_progress_cluster_step'),
    )


def upgrade():
    _add_flow_columns()
    _add_cluster_flow_column()
    _create_alert_cluster_investigation_progress()


def downgrade():
    op.drop_table('alert_cluster_investigation_progress')
    if _table_has_column('alert_clusters', 'cluster_investigation_flow_id'):
        op.drop_column('alert_clusters', 'cluster_investigation_flow_id')
    if _table_has_column('investigation_flows', 'flow_priority'):
        op.drop_column('investigation_flows', 'flow_priority')
    if _table_has_column('investigation_flows', 'flow_conditions'):
        op.drop_column('investigation_flows', 'flow_conditions')
    if _table_has_column('investigation_flows', 'flow_target'):
        op.drop_column('investigation_flows', 'flow_target')
