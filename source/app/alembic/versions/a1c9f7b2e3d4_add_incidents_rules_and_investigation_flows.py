"""Add incidents, incident rules, and investigation flows.

Creates the tables backing the alert-stacking + guided-triage features:

  * `incident_status` — lookup (Open / Investigating / Dismissed / Escalated)
  * `incidents` — the alert-container entity
  * `alert_incident_association` — N:N alerts↔incidents
  * `incident_rules` — flexible auto-stacking + auto-flow-attach rules
  * `investigation_flows` — named checklist definitions
  * `investigation_flow_steps` — ordered steps per flow
  * `alert_investigation_progress` — per-alert step check-offs
  * `alerts.alert_investigation_flow_id` — cached flow attachment on an alert

Every step is guarded by `_has_table` / `_table_has_column` so the migration
is idempotent — safe to re-run on partially-upgraded environments. Permission
flags are enum bitmasks on `Group.group_permissions` (no DB rows to seed).
The four IncidentStatus rows are seeded by `post_init.create_safe_incident_status()`
at boot, not by the migration, to match how AlertStatus / AlertResolutionStatus
are handled.

Revision ID: a1c9f7b2e3d4
Revises: f2b6a4d19e3c
Create Date: 2026-07-02 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

from app.alembic.alembic_utils import _has_table
from app.alembic.alembic_utils import _table_has_column


revision = 'a1c9f7b2e3d4'
down_revision = 'f2b6a4d19e3c'
branch_labels = None
depends_on = None


def _create_incident_status():
    if _has_table('incident_status'):
        return
    op.create_table(
        'incident_status',
        sa.Column('status_id', sa.Integer(), primary_key=True),
        sa.Column('status_name', sa.Text(), nullable=False),
        sa.Column('status_description', sa.Text(), nullable=True),
        sa.UniqueConstraint('status_name', name='uq_incident_status_name'),
    )


def _create_incident_rules():
    if _has_table('incident_rules'):
        return
    op.create_table(
        'incident_rules',
        sa.Column('rule_id', sa.BigInteger(), primary_key=True),
        sa.Column('rule_uuid', sa.dialects.postgresql.UUID(as_uuid=True),
                  nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('rule_name', sa.Text(), nullable=False),
        sa.Column('rule_description', sa.Text(), nullable=True),
        sa.Column('rule_is_active', sa.Boolean(), nullable=False,
                  server_default=sa.text('true')),
        sa.Column('rule_priority', sa.Integer(), nullable=False,
                  server_default=sa.text('100')),
        sa.Column('rule_customer_scope', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('rule_conditions', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('rule_action_type', sa.Text(), nullable=False),
        sa.Column('rule_action_config', sa.dialects.postgresql.JSONB(),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('rule_created_by', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.Column('rule_created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('rule_updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.UniqueConstraint('rule_uuid', name='uq_incident_rules_uuid'),
    )


def _create_investigation_flows():
    if _has_table('investigation_flows'):
        return
    op.create_table(
        'investigation_flows',
        sa.Column('flow_id', sa.BigInteger(), primary_key=True),
        sa.Column('flow_uuid', sa.dialects.postgresql.UUID(as_uuid=True),
                  nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('flow_name', sa.Text(), nullable=False),
        sa.Column('flow_description', sa.Text(), nullable=True),
        sa.Column('flow_is_active', sa.Boolean(), nullable=False,
                  server_default=sa.text('true')),
        sa.Column('flow_customer_scope', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('flow_created_by', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.Column('flow_created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('flow_updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.UniqueConstraint('flow_uuid', name='uq_investigation_flows_uuid'),
    )


def _create_investigation_flow_steps():
    if _has_table('investigation_flow_steps'):
        return
    op.create_table(
        'investigation_flow_steps',
        sa.Column('step_id', sa.BigInteger(), primary_key=True),
        sa.Column('flow_id', sa.BigInteger(),
                  sa.ForeignKey('investigation_flows.flow_id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('step_title', sa.Text(), nullable=False),
        sa.Column('step_description', sa.Text(), nullable=True),
        sa.Column('step_is_required', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')),
    )


def _add_alert_investigation_flow_column():
    if _table_has_column('alerts', 'alert_investigation_flow_id'):
        return
    op.add_column(
        'alerts',
        sa.Column('alert_investigation_flow_id', sa.BigInteger(),
                  sa.ForeignKey('investigation_flows.flow_id'), nullable=True),
    )


def _create_incidents():
    if _has_table('incidents'):
        return
    op.create_table(
        'incidents',
        sa.Column('incident_id', sa.BigInteger(), primary_key=True),
        sa.Column('incident_uuid', sa.dialects.postgresql.UUID(as_uuid=True),
                  nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('incident_title', sa.Text(), nullable=False),
        sa.Column('incident_description', sa.Text(), nullable=True),
        sa.Column('incident_status_id', sa.Integer(),
                  sa.ForeignKey('incident_status.status_id'), nullable=False),
        sa.Column('incident_severity_id', sa.Integer(),
                  sa.ForeignKey('severities.severity_id'), nullable=True),
        sa.Column('incident_customer_id', sa.BigInteger(),
                  sa.ForeignKey('client.client_id'), nullable=False),
        sa.Column('incident_owner_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=True),
        sa.Column('incident_creation_time', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('incident_source_rule_id', sa.BigInteger(),
                  sa.ForeignKey('incident_rules.rule_id'), nullable=True),
        sa.Column('incident_case_id', sa.BigInteger(),
                  sa.ForeignKey('cases.case_id'), nullable=True),
        sa.Column('incident_dedupe_key', sa.Text(), nullable=True, index=True),
        sa.Column('modification_history', sa.dialects.postgresql.JSON(), nullable=True),
        sa.UniqueConstraint('incident_uuid', name='uq_incidents_uuid'),
    )


def _create_alert_incident_association():
    if _has_table('alert_incident_association'):
        return
    op.create_table(
        'alert_incident_association',
        sa.Column('alert_id', sa.BigInteger(),
                  sa.ForeignKey('alerts.alert_id'), primary_key=True, nullable=False),
        sa.Column('incident_id', sa.BigInteger(),
                  sa.ForeignKey('incidents.incident_id'), primary_key=True,
                  nullable=False, index=True),
    )


def _create_alert_investigation_progress():
    if _has_table('alert_investigation_progress'):
        return
    op.create_table(
        'alert_investigation_progress',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('alert_id', sa.BigInteger(),
                  sa.ForeignKey('alerts.alert_id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('step_id', sa.BigInteger(),
                  sa.ForeignKey('investigation_flow_steps.step_id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('completed_by_user_id', sa.BigInteger(),
                  sa.ForeignKey('user.id'), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('note', sa.Text(), nullable=True),
        sa.UniqueConstraint('alert_id', 'step_id',
                            name='uq_alert_investigation_progress_alert_step'),
    )


def upgrade():
    _create_incident_status()
    _create_incident_rules()
    _create_investigation_flows()
    _create_investigation_flow_steps()
    _add_alert_investigation_flow_column()
    _create_incidents()
    _create_alert_incident_association()
    _create_alert_investigation_progress()


def downgrade():
    op.drop_table('alert_investigation_progress')
    op.drop_table('alert_incident_association')
    op.drop_table('incidents')
    if _table_has_column('alerts', 'alert_investigation_flow_id'):
        op.drop_column('alerts', 'alert_investigation_flow_id')
    op.drop_table('investigation_flow_steps')
    op.drop_table('investigation_flows')
    op.drop_table('incident_rules')
    op.drop_table('incident_status')
