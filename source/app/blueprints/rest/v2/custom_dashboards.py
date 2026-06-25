#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint
from flask import request
from marshmallow import ValidationError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.datamgmt.custom_dashboard.custom_dashboard_db import (
    DashboardAccessError,
    DashboardNotFoundError,
    DashboardSystemReadOnlyError,
    create_dashboard_for_user,
    delete_dashboard_for_user,
    get_dashboard_for_user,
    list_dashboards_for_user,
    serialize_dashboard,
    update_dashboard_for_user,
)
from app.datamgmt.custom_dashboard.named_aggregations import (
    ComputedFilters,
    NamedAggregationError,
    compute_named_aggregation,
    list_named_aggregations,
)
from app.datamgmt.custom_dashboard.query_engine import (
    QueryExecutionError,
    WidgetQueryExecutor,
    format_widget_payload,
)
from app.datamgmt.custom_dashboard.schema import CustomDashboardSchema
from app.blueprints.access_controls import ac_current_user_has_permission
from app.models.authorization import Permissions


custom_dashboards_blueprint = Blueprint(
    'custom_dashboards',
    __name__,
    url_prefix='/custom-dashboards',
)


_WIDGET_PRESETS: List[Dict[str, Any]] = [
    {
        'id': 'preset-alerts-by-severity',
        'name': 'Alerts by severity',
        'chart_type': 'pie',
        'fields': [
            {'table': 'severities', 'column': 'severity_name', 'alias': 'severity'},
            {'table': 'alerts', 'column': 'alert_id', 'aggregation': 'count', 'alias': 'total'},
        ],
        'group_by': ['severities.severity_name'],
    },
    {
        'id': 'preset-cases-by-classification',
        'name': 'Cases by classification',
        'chart_type': 'bar',
        'fields': [
            {'table': 'case_classification', 'column': 'name_expanded', 'alias': 'classification'},
            {'table': 'cases', 'column': 'case_id', 'aggregation': 'count', 'alias': 'total'},
        ],
        'group_by': ['case_classification.name_expanded'],
    },
    {
        'id': 'preset-evidence-by-type',
        'name': 'Evidence by type',
        'chart_type': 'bar',
        'fields': [
            {'table': 'case_asset_types', 'column': 'asset_name', 'alias': 'asset_type'},
            {'table': 'case_assets', 'column': 'asset_id', 'aggregation': 'count', 'alias': 'total'},
        ],
        'group_by': ['case_asset_types.asset_name'],
    },
    {
        'id': 'preset-mttd-kpi',
        'name': 'Mean time to detect',
        'chart_type': 'number',
        'fields': [{'table': 'computed', 'column': 'mttd_seconds', 'alias': 'mttd_seconds'}],
        'options': {'value_format': 'duration'},
    },
    {
        'id': 'preset-mttr-kpi',
        'name': 'Mean time to resolve',
        'chart_type': 'number',
        'fields': [{'table': 'computed', 'column': 'mttr_seconds', 'alias': 'mttr_seconds'}],
        'options': {'value_format': 'duration'},
    },
]


def _parse_datetime_param(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


def _extract_timeframe(payload: Dict[str, Any]) -> Tuple[Optional[datetime], Optional[datetime]]:
    timeframe = payload.get('timeframe') or {}
    return (
        _parse_datetime_param(timeframe.get('start')),
        _parse_datetime_param(timeframe.get('end')),
    )


def _extract_filters(payload: Dict[str, Any]) -> ComputedFilters:
    filters = payload.get('filters') or {}
    return ComputedFilters(
        customer_id=filters.get('customer_id') if isinstance(filters.get('customer_id'), int) else None,
        severity_id=filters.get('severity_id') if isinstance(filters.get('severity_id'), int) else None,
        case_status_id=filters.get('case_status_id') if isinstance(filters.get('case_status_id'), int) else None,
        window=filters.get('window') if isinstance(filters.get('window'), str) else None,
    )


def _widget_references_computed(widget: Dict[str, Any]) -> Optional[str]:
    for field in widget.get('fields') or []:
        if not isinstance(field, dict):
            continue
        if field.get('table') == 'computed':
            return field.get('column')
    return None


def _render_widget(
    widget: Dict[str, Any],
    timeframe: Tuple[Optional[datetime], Optional[datetime]],
    filters: ComputedFilters,
) -> Dict[str, Any]:
    computed_name = _widget_references_computed(widget)
    if computed_name:
        try:
            value = compute_named_aggregation(computed_name, timeframe, filters)
        except NamedAggregationError as e:
            raise QueryExecutionError(str(e))
        return {
            'name': widget.get('name'),
            'chart_type': widget.get('chart_type', 'number'),
            'computed': computed_name,
            'value': value,
            'options': widget.get('options') or {},
            'layout': widget.get('layout') or {},
        }

    executor = WidgetQueryExecutor(widget)
    result = executor.execute(timeframe)
    payload = format_widget_payload(result, widget, timeframe)
    payload['name'] = widget.get('name')
    payload['chart_type'] = widget.get('chart_type')
    payload['layout'] = widget.get('layout') or {}
    return payload


@custom_dashboards_blueprint.get('')
@ac_api_requires(Permissions.custom_dashboards_read)
def list_dashboards():
    dashboards = list_dashboards_for_user(iris_current_user.id)
    return response_api_success(data=[serialize_dashboard(d) for d in dashboards])


@custom_dashboards_blueprint.get('/schema')
@ac_api_requires(Permissions.custom_dashboards_read)
def get_editor_schema():
    schema = {
        'tables': list(WidgetQueryExecutor._TABLES.keys()),
        'columns': {
            name: list(table['columns'].keys())
            for name, table in WidgetQueryExecutor._TABLES.items()
        },
        'named_aggregations': list_named_aggregations(),
        'aggregations': ['count', 'sum', 'avg', 'min', 'max', 'ratio'],
        'operators': ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'in', 'nin', 'between', 'contains'],
        'chart_types': ['line', 'bar', 'pie', 'number', 'percentage', 'table', 'timechart'],
        'time_buckets': ['minute', '5minute', '15minute', 'hour', 'day', 'week', 'month', 'year'],
    }
    return response_api_success(data=schema)


@custom_dashboards_blueprint.get('/presets')
@ac_api_requires(Permissions.custom_dashboards_read)
def get_presets():
    return response_api_success(data=_WIDGET_PRESETS)


@custom_dashboards_blueprint.get('/<dashboard_uuid>')
@ac_api_requires(Permissions.custom_dashboards_read)
def get_dashboard(dashboard_uuid: str):
    try:
        dashboard = get_dashboard_for_user(dashboard_uuid, iris_current_user.id)
    except DashboardNotFoundError:
        return response_api_not_found()
    except DashboardAccessError:
        return response_api_error('Dashboard is not accessible.')
    return response_api_success(data=serialize_dashboard(dashboard))


@custom_dashboards_blueprint.post('')
@ac_api_requires(Permissions.custom_dashboards_write)
def create_dashboard():
    payload = request.get_json(silent=True) or {}
    schema = CustomDashboardSchema()
    try:
        schema.load(payload)
    except ValidationError as e:
        return response_api_error('Invalid dashboard payload.', data=e.messages)

    allow_share = ac_current_user_has_permission(Permissions.custom_dashboards_share)
    dashboard = create_dashboard_for_user(iris_current_user.id, payload, allow_share)
    return response_api_created(data=serialize_dashboard(dashboard))


@custom_dashboards_blueprint.put('/<dashboard_uuid>')
@ac_api_requires(Permissions.custom_dashboards_write)
def update_dashboard(dashboard_uuid: str):
    payload = request.get_json(silent=True) or {}
    schema = CustomDashboardSchema(partial=True)
    try:
        schema.load(payload)
    except ValidationError as e:
        return response_api_error('Invalid dashboard payload.', data=e.messages)

    allow_share = ac_current_user_has_permission(Permissions.custom_dashboards_share)
    try:
        dashboard = update_dashboard_for_user(dashboard_uuid, iris_current_user.id, payload, allow_share)
    except DashboardNotFoundError:
        return response_api_not_found()
    except DashboardSystemReadOnlyError:
        return response_api_error('System dashboards cannot be modified through the API.')
    except DashboardAccessError:
        return response_api_error('Dashboard is not accessible.')
    return response_api_success(data=serialize_dashboard(dashboard))


@custom_dashboards_blueprint.delete('/<dashboard_uuid>')
@ac_api_requires(Permissions.custom_dashboards_write)
def delete_dashboard(dashboard_uuid: str):
    try:
        delete_dashboard_for_user(dashboard_uuid, iris_current_user.id)
    except DashboardNotFoundError:
        return response_api_not_found()
    except DashboardSystemReadOnlyError:
        return response_api_error('System dashboards cannot be deleted through the API.')
    except DashboardAccessError:
        return response_api_error('Dashboard is not accessible.')
    return response_api_deleted()


@custom_dashboards_blueprint.post('/<dashboard_uuid>/render')
@ac_api_requires(Permissions.custom_dashboards_read)
def render_dashboard(dashboard_uuid: str):
    try:
        get_dashboard_for_user(dashboard_uuid, iris_current_user.id)
    except DashboardNotFoundError:
        return response_api_not_found()
    except DashboardAccessError:
        return response_api_error('Dashboard is not accessible.')

    payload = request.get_json(silent=True) or {}
    definition = payload.get('definition') or {}
    schema = CustomDashboardSchema(partial=True)
    try:
        schema.load(definition)
    except ValidationError as e:
        return response_api_error('Invalid dashboard definition.', data=e.messages)

    timeframe = _extract_timeframe(payload)
    filters = _extract_filters(payload)

    sections = definition.get('sections') or []
    widgets: List[Dict[str, Any]] = []
    if sections:
        for section in sections:
            for widget in section.get('widgets') or []:
                widgets.append(widget)
    else:
        widgets = definition.get('widgets') or []

    rendered: List[Dict[str, Any]] = []
    for widget in widgets:
        try:
            rendered.append(_render_widget(widget, timeframe, filters))
        except QueryExecutionError as e:
            rendered.append({
                'name': widget.get('name'),
                'chart_type': widget.get('chart_type'),
                'error': str(e),
                'layout': widget.get('layout') or {},
            })

    return response_api_success(data={'widgets': rendered})
