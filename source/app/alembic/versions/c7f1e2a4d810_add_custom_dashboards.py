"""Add custom dashboards tables and seed Statistics dashboard

Revision ID: c7f1e2a4d810
Revises: afcff5ebcf7c
Create Date: 2026-06-25 10:00:00.000000

"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import table, column

from app.alembic.alembic_utils import _has_table, _table_has_column


revision = 'c7f1e2a4d810'
down_revision = 'afcff5ebcf7c'
branch_labels = None
depends_on = None


STATISTICS_DASHBOARD_UUID = '00000000-0000-4000-8000-000000000001'


def _statistics_definition():
    return {
        'name': 'Statistics',
        'description': 'Built-in IRIS statistics dashboard. Clone to customise.',
        'is_shared': True,
        'is_system': True,
        'filters_schema': [
            {'key': 'start', 'label': 'Start date', 'type': 'date'},
            {'key': 'end', 'label': 'End date', 'type': 'date'},
            {'key': 'customer_id', 'label': 'Customer', 'type': 'reference', 'table': 'client', 'column': 'client_id'},
            {'key': 'severity_id', 'label': 'Severity', 'type': 'reference', 'table': 'severities', 'column': 'severity_id'},
            {'key': 'case_status_id', 'label': 'Case status', 'type': 'reference', 'table': 'case_state', 'column': 'state_id'}
        ],
        'sections': [
            {
                'id': 'section-kpis',
                'title': 'Key indicators',
                'description': 'Headline volumes and response times.',
                'show_divider': False,
                'widgets': [
                    {
                        'name': 'Total alerts',
                        'chart_type': 'number',
                        'fields': [{'table': 'alerts', 'column': 'alert_id', 'aggregation': 'count', 'alias': 'total_alerts'}],
                        'layout': {'widget_size': 'kpi'}
                    },
                    {
                        'name': 'Total cases',
                        'chart_type': 'number',
                        'fields': [{'table': 'cases', 'column': 'case_id', 'aggregation': 'count', 'alias': 'total_cases'}],
                        'layout': {'widget_size': 'kpi'}
                    },
                    {
                        'name': 'Mean time to detect',
                        'chart_type': 'number',
                        'fields': [{'table': 'computed', 'column': 'mttd_seconds', 'alias': 'mttd_seconds'}],
                        'options': {'value_format': 'duration'},
                        'layout': {'widget_size': 'kpi'}
                    },
                    {
                        'name': 'Mean time to resolve',
                        'chart_type': 'number',
                        'fields': [{'table': 'computed', 'column': 'mttr_seconds', 'alias': 'mttr_seconds'}],
                        'options': {'value_format': 'duration'},
                        'layout': {'widget_size': 'kpi'}
                    }
                ]
            },
            {
                'id': 'section-charts',
                'title': 'Distributions',
                'description': 'How alerts, cases and evidence break down across the selected window.',
                'show_divider': True,
                'widgets': [
                    {
                        'name': 'Alerts by severity',
                        'chart_type': 'pie',
                        'fields': [
                            {'table': 'alerts', 'column': 'alert_id', 'aggregation': 'count', 'alias': 'total'}
                        ],
                        'group_by': ['severities.severity_name'],
                        'layout': {'widget_size': 'half'}
                    },
                    {
                        'name': 'Cases by classification',
                        'chart_type': 'bar',
                        'fields': [
                            {'table': 'cases', 'column': 'case_id', 'aggregation': 'count', 'alias': 'total'}
                        ],
                        'group_by': ['case_classification.name_expanded'],
                        'layout': {'widget_size': 'half'}
                    },
                    {
                        'name': 'Evidence by type',
                        'chart_type': 'bar',
                        'fields': [
                            {'table': 'case_assets', 'column': 'asset_id', 'aggregation': 'count', 'alias': 'total'}
                        ],
                        'group_by': ['case_asset_types.asset_name'],
                        'layout': {'widget_size': 'full'}
                    }
                ]
            }
        ]
    }


def upgrade():
    if not _has_table('custom_dashboard'):
        op.create_table(
            'custom_dashboard',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('dashboard_uuid', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False, unique=True),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('owner_id', sa.Integer, sa.ForeignKey('user.id'), nullable=True),
            sa.Column('is_shared', sa.Boolean, nullable=False, server_default=sa.text('false')),
            sa.Column('is_system', sa.Boolean, nullable=False, server_default=sa.text('false')),
            sa.Column('definition', postgresql.JSONB, nullable=True),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
        )

    # Reconcile pre-existing custom_dashboard table (e.g. created by a prior
    # alembic head or by SQLAlchemy metadata) with the schema this migration
    # expects. Add is_system if missing, relax owner_id NOT NULL so system
    # rows can be seeded.
    if _has_table('custom_dashboard'):
        if not _table_has_column('custom_dashboard', 'is_system'):
            op.add_column(
                'custom_dashboard',
                sa.Column('is_system', sa.Boolean, nullable=False, server_default=sa.text('false')),
            )
        op.execute(sa.text('ALTER TABLE custom_dashboard ALTER COLUMN owner_id DROP NOT NULL'))

    if not _has_table('custom_dashboard_widget'):
        op.create_table(
            'custom_dashboard_widget',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('widget_uuid', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False, unique=True),
            sa.Column('dashboard_id', sa.Integer, sa.ForeignKey('custom_dashboard.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('chart_type', sa.String(length=64), nullable=False),
            sa.Column('definition', postgresql.JSONB, nullable=False),
            sa.Column('position', sa.Integer, nullable=False, server_default=sa.text('0')),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
        )
        op.create_index('ix_custom_dashboard_widget_dashboard_id', 'custom_dashboard_widget', ['dashboard_id'])

    dashboard_table = table(
        'custom_dashboard',
        column('dashboard_uuid', postgresql.UUID(as_uuid=True)),
        column('name', sa.String),
        column('description', sa.Text),
        column('owner_id', sa.Integer),
        column('is_shared', sa.Boolean),
        column('is_system', sa.Boolean),
        column('definition', postgresql.JSONB)
    )
    widget_table = table(
        'custom_dashboard_widget',
        column('dashboard_id', sa.Integer),
        column('name', sa.String),
        column('chart_type', sa.String),
        column('definition', postgresql.JSONB),
        column('position', sa.Integer)
    )

    bind = op.get_bind()
    existing = bind.execute(
        sa.text('SELECT id FROM custom_dashboard WHERE dashboard_uuid = :u'),
        {'u': STATISTICS_DASHBOARD_UUID}
    ).fetchone()
    if existing is not None:
        return

    definition = _statistics_definition()
    op.bulk_insert(dashboard_table, [{
        'dashboard_uuid': STATISTICS_DASHBOARD_UUID,
        'name': definition['name'],
        'description': definition['description'],
        'owner_id': None,
        'is_shared': True,
        'is_system': True,
        'definition': definition
    }])

    inserted = bind.execute(
        sa.text('SELECT id FROM custom_dashboard WHERE dashboard_uuid = :u'),
        {'u': STATISTICS_DASHBOARD_UUID}
    ).fetchone()
    if inserted is None:
        return
    dashboard_id = inserted[0]

    widgets = []
    position = 0
    for section in definition.get('sections', []):
        for widget in section.get('widgets', []):
            widget_payload = dict(widget)
            widget_payload.setdefault('layout', {})['section_id'] = section.get('id')
            widget_payload['layout']['section_title'] = section.get('title')
            widgets.append({
                'dashboard_id': dashboard_id,
                'name': widget['name'],
                'chart_type': widget['chart_type'],
                'definition': widget_payload,
                'position': position
            })
            position += 1
    if widgets:
        op.bulk_insert(widget_table, widgets)


def downgrade():
    if _has_table('custom_dashboard_widget'):
        op.drop_index('ix_custom_dashboard_widget_dashboard_id', table_name='custom_dashboard_widget')
        op.drop_table('custom_dashboard_widget')

    if _has_table('custom_dashboard'):
        op.drop_table('custom_dashboard')
