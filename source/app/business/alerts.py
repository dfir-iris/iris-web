#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

import json
from datetime import datetime
from typing import Optional

from app.business.access_controls import access_controls_user_has_customer_access
from app.db import db
from app import socket_io
from app.models.alerts import Alert
from app.models.iocs import Ioc
from app.models.assets import CaseAssets
from app.datamgmt.alerts.alerts_db import cache_similar_alert
from app.datamgmt.alerts.alerts_db import delete_similar_alert_cache
from app.datamgmt.alerts.alerts_db import delete_related_alerts_cache
from app.datamgmt.alerts.alerts_db import get_alert_by_id
from app.datamgmt.alerts.alerts_db import delete_alert
from app.datamgmt.alerts.alerts_db import get_filtered_alerts
from app.datamgmt.alerts.alerts_db import get_related_alerts_details
from app.datamgmt.alerts.alerts_db import get_assets_with_cases
from app.datamgmt.alerts.alerts_db import get_iocs_with_cases
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.util import add_obj_history_entry
from app.models.errors import ObjectNotFoundError


def alerts_search(start_date, end_date, source_start_date, source_end_date, title, description,
                  status, severity, owner, source, tags, case_identifier, customer_identifier, classification, alert_identifiers,
                  assets, iocs, resolution_status, source_reference, custom_conditions, user_identifier_filter, page, per_page, sort,
                  cluster_identifier=None):

    return get_filtered_alerts(
        start_date,
        end_date,
        source_start_date,
        source_end_date,
        title,
        description,
        status,
        severity,
        owner,
        source,
        tags,
        case_identifier,
        customer_identifier,
        classification,
        alert_identifiers,
        assets,
        iocs,
        resolution_status,
        page,
        per_page,
        sort,
        user_identifier_filter,
        source_reference,
        custom_conditions,
        cluster_id=cluster_identifier,
    )


def alerts_create(alert: Alert, iocs: list[Ioc], assets: list[CaseAssets]) -> Alert:

    alert.alert_creation_time = datetime.utcnow()

    alert.iocs = iocs
    alert.assets = assets

    db.session.add(alert)
    db.session.commit()

    add_obj_history_entry(alert, 'Alert created')

    cache_similar_alert(alert.alert_customer_id, assets, iocs, alert.alert_id, alert.alert_source_event_time)

    alert = call_modules_hook('on_postload_alert_create', alert)

    track_activity(f"created alert #{alert.alert_id} - {alert.alert_title}", ctx_less=True)

    socket_io.emit('new_alert', json.dumps({
        'alert_id': alert.alert_id
    }), namespace='/alerts')

    _enqueue_rule_evaluation(alert.alert_id)

    return alert


def _enqueue_rule_evaluation(alert_id: int) -> None:
    """Fire the async rule evaluator. Import is deferred so a broken/
    unregistered Celery worker doesn't crash the request path — the
    ImportError branch logs and swallows so alert ingestion still
    succeeds even if the cluster-rules feature is disabled or the
    worker module fails to load."""
    try:
        from app.iris_engine.cluster_rules.tasks import evaluate_alert_rules
        evaluate_alert_rules.delay(alert_id)
    except Exception:  # noqa: BLE001 — rule evaluation must never block alert ingestion
        from app.logger import logger
        logger.exception('Failed to enqueue rule evaluation for alert #%s', alert_id)


def _get(user, permissions, identifier, fallback_customer_access=None) -> Optional[Alert]:
    alert = get_alert_by_id(identifier)
    if not alert:
        return None
    if not access_controls_user_has_customer_access(
        user,
        permissions,
        alert.alert_customer_id,
        fallback_customer_access=fallback_customer_access
    ):
        return None
    return alert


def alerts_get(user, permissions, identifier, fallback_customer_access=None) -> Alert:
    alert = _get(user, permissions, identifier, fallback_customer_access=fallback_customer_access)
    if not alert:
        raise ObjectNotFoundError()
    return alert


# TODO this is presentation code, should be in the presentation layer (frontend) rather than in the persistence layer!
def _get_font(in_dark_mode) -> str:
    if in_dark_mode:
        return '12px verdana white'
    return ''


# TODO this is presentation code, should be in the presentation layer (frontend) rather than in the persistence layer!
def _get_icon_alert(alert_color) -> dict[str, str]:
    return {
        'face': 'FontAwesome',
        'code': '\uf0f3',
        'color': alert_color,
        'weight': 'bold'
    }


# TODO this is presentation code, should be in the presentation layer (frontend) rather than in the persistence layer!
def _get_icon_ioc(in_dark_mode) -> dict[str, str]:
    return {
        'face': 'FontAwesome',
        'code': '\ue4a8',
        'color': 'white' if in_dark_mode else '',
        'weight': "bold"
    }


# TODO this is presentation code, should be in the presentation layer (frontend) rather than in the persistence layer!
def _get_icon_case(is_closed) -> dict[str, str]:
    return {
        'face': 'FontAwesome',
        'code': '\uf0b1',
        'color': '#c95029' if is_closed else '#4cba4f'
    }


def _create_alert_node(alert_id, alert_info, in_dark_mode):
    alert_color = '#c95029' if alert_info['alert'].status.status_name in ['Closed', 'Merged', 'Escalated'] else ''
    alert_resolution_title = f'[{alert_info["alert"].resolution_status.resolution_status_name}]\n' if alert_info[
        "alert"].resolution_status else ""
    alert_node = {
        'id': f'alert_{alert_id}',
        'label': f'[Closed]{alert_resolution_title} {alert_info["alert"].alert_title}' if alert_color != '' else f'{alert_resolution_title}{alert_info["alert"].alert_title}',
        'title': f'{alert_info["alert"].alert_description}',
        'group': 'alert',
        'shape': 'icon',
        'icon': _get_icon_alert(alert_color),
        'font': _get_font(in_dark_mode)
    }
    return alert_node


def _create_ioc_node(in_dark_mode, ioc_value):
    return {
        'id': f'ioc_{ioc_value}',
        'label': ioc_value,
        'group': 'ioc',
        'shape': 'icon',
        'icon': _get_icon_ioc(in_dark_mode),
        'font': _get_font(in_dark_mode)
    }


def _create_asset_node(asset_id, asset_info, in_dark_mode):
    return {
        'id': f'asset_{asset_id}',
        'label': asset_id,
        'group': 'asset',
        'shape': 'image',
        'image': '/static/assets/img/graph/' + asset_info['icon'],
        'font': _get_font(in_dark_mode)
    }


def _create_case_node(case_id, description, close_date, in_dark_mode):
    return {
        'id': f'case_{case_id}',
        'label': f'[Closed] Case #{case_id}' if close_date else f'Case #{case_id}',
        'title': description,
        'group': 'case',
        'shape': 'icon',
        'icon': _get_icon_case(close_date),
        'font': _get_font(in_dark_mode)
    }


def _build_related_alerts_graph(alerts_dict, open_cases, closed_cases, customer_id, in_dark_mode):
    nodes = []
    edges = []

    added_assets = set()
    added_iocs = set()

    for alert_id, alert_info in alerts_dict.items():
        alert_node = _create_alert_node(alert_id, alert_info, in_dark_mode)
        nodes.append(alert_node)

        for asset_info in alert_info['assets']:
            asset_id = asset_info['asset_name']

            if asset_id not in added_assets:
                nodes.append(_create_asset_node(asset_id, asset_info, in_dark_mode))
                added_assets.add(asset_id)

            edges.append({
                'from': f'alert_{alert_id}',
                'to': f'asset_{asset_id}'
            })

        for ioc_value in alert_info['iocs']:
            if ioc_value not in added_iocs:
                nodes.append(_create_ioc_node(in_dark_mode, ioc_value))
                added_iocs.add(ioc_value)

            edges.append({
                'from': f'alert_{alert_id}',
                'to': f'ioc_{ioc_value}',
                'dashes': True
            })

    if open_cases or closed_cases:

        cases_data = {}

        matching_ioc_cases = get_iocs_with_cases(added_iocs, customer_id, open_cases, closed_cases)
        for case_id, ioc_value, case_name, close_date, case_desc in matching_ioc_cases:
            if case_id not in cases_data:
                cases_data[case_id] = {'name': case_name, 'matching_ioc': [], 'matching_assets': [],
                                       'close_date': close_date, 'description': case_desc}
            cases_data[case_id]['matching_ioc'].append(ioc_value)

        matching_asset_cases = get_assets_with_cases(added_assets, customer_id, open_cases, closed_cases)
        for case_id, asset_name, case_name, close_date, case_desc in matching_asset_cases:
            if case_id not in cases_data:
                cases_data[case_id] = {'name': case_name, 'matching_ioc': [], 'matching_assets': [],
                                       'close_date': close_date, 'description': case_desc}
            cases_data[case_id]['matching_assets'].append(asset_name)

        added_cases = set()
        for case_id in cases_data:
            case_data = cases_data[case_id]
            if case_id not in added_cases:
                close_date = case_data.get('close_date')
                description = case_data.get('description')
                nodes.append(_create_case_node(case_id, description, close_date, in_dark_mode))
                added_cases.add(case_id)

            for ioc_value in case_data['matching_ioc']:
                edges.append({
                    'from': f'ioc_{ioc_value}',
                    'to': f'case_{case_id}',
                    'dashes': True
                })

            for asset_name in case_data['matching_assets']:
                edges.append({
                    'from': f'asset_{asset_name}',
                    'to': f'case_{case_id}',
                    'dashes': True
                })

    return {
        'nodes': nodes,
        'edges': edges
    }


def alerts_get_related(user, alert, open_alerts, closed_alerts, open_cases, closed_cases, days_back, number_of_results):
    assets = alert.assets
    iocs = alert.iocs
    if not assets and not iocs:
        return {
            'nodes': [],
            'edges': []
        }

    in_dark_mode = getattr(user, 'in_dark_mode', False)
    alerts_dict = get_related_alerts_details(alert.alert_customer_id, assets, iocs, open_alerts, closed_alerts,
                                             days_back, number_of_results)
    return _build_related_alerts_graph(alerts_dict, open_cases, closed_cases, alert.alert_customer_id, in_dark_mode)


def alerts_exists(user, permissions, identifier, fallback_customer_access=None) -> bool:
    alert = _get(user, permissions, identifier, fallback_customer_access=fallback_customer_access)

    return alert is not None


def alerts_update(alert: Alert, updated_alert: Alert, activity_data) -> Alert:

    do_resolution_hook = False
    do_status_hook = False

    if alert.alert_resolution_status_id != updated_alert.alert_resolution_status_id:
        do_resolution_hook = True
    if alert.alert_status_id != updated_alert.alert_status_id:
        do_status_hook = True

    updated_alert = call_modules_hook('on_postload_alert_update', updated_alert)

    if do_resolution_hook:
        updated_alert = call_modules_hook('on_postload_alert_resolution_update', updated_alert)

    if do_status_hook:
        updated_alert = call_modules_hook('on_postload_alert_status_update', updated_alert)

    if activity_data:
        activity_data_as_string = ','.join(activity_data)
        track_activity(f'updated alert #{alert.alert_id}: {activity_data_as_string}', ctx_less=True)
        add_obj_history_entry(updated_alert, f'updated alert: {activity_data_as_string}')
    else:
        track_activity(f'updated alert #{alert.alert_id}', ctx_less=True)
        add_obj_history_entry(updated_alert, 'updated alert')

    db.session.commit()
    _enqueue_rule_evaluation(updated_alert.alert_id)
    return updated_alert


def alerts_delete(alert: Alert):

    delete_similar_alert_cache(alert.alert_id)
    delete_related_alerts_cache([alert.alert_id])
    delete_alert(alert)

    call_modules_hook('on_postload_alert_delete', alert.alert_id)
    track_activity(f'delete alert #{alert.alert_id}', ctx_less=True)
