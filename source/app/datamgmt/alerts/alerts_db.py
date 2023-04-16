#!/usr/bin/env python3
#
#  IRIS Source Code
#  Copyright (C) 2023 - DFIR-IRIS
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

from flask_login import current_user
from operator import and_
from sqlalchemy import desc, asc
from sqlalchemy.orm import joinedload
from typing import List, Tuple

import app
from app import db
from app.datamgmt.case.case_assets_db import create_asset, set_ioc_links, get_unspecified_analysis_status_id
from app.datamgmt.case.case_events_db import update_event_assets, update_event_iocs
from app.datamgmt.case.case_iocs_db import add_ioc, add_ioc_link
from app.datamgmt.states import update_timeline_state
from app.models import Cases, EventCategory, Tags, AssetsType, Comments
from app.models.alerts import Alert, AlertStatus, AlertCaseAssociation, SimilarAlertsCache
from app.schema.marshables import IocSchema, CaseAssetsSchema, EventSchema
from app.util import add_obj_history_entry

from sqlalchemy.orm import aliased


def db_list_all_alerts():
    """
    List all alerts in the database
    """
    return db.session.query(Alert).all()


def get_filtered_alerts(
        start_date: str = None,
        end_date: str = None,
        title: str = None,
        description: str = None,
        status: int = None,
        severity: int = None,
        owner: int = None,
        source: str = None,
        tags: str = None,
        case_id: int = None,
        client: int = None,
        classification: int = None,
        alert_id: int = None,
        page: int = 1,
        per_page: int = 10,
        sort: str = 'desc'
):
    """
    Get a list of alerts that match the given filter conditions

    args:
        start_date (datetime): The start date of the alert creation time
        end_date (datetime): The end date of the alert creation time
        title (str): The title of the alert
        description (str): The description of the alert
        status (str): The status of the alert
        severity (str): The severity of the alert
        owner (str): The owner of the alert
        source (str): The source of the alert
        tags (str): The tags of the alert
        case_id (int): The case id of the alert
        client (int): The client id of the alert
        classification (int): The classification id of the alert
        alert_id (int): The alert id
        page (int): The page number
        per_page (int): The number of alerts per page
        sort (str): The sort order

    returns:
        list: A list of alerts that match the given filter conditions
    """
    # Build the filter conditions
    conditions = []

    if start_date is not None and end_date is not None:
        conditions.append(Alert.alert_creation_time.between(start_date, end_date))

    if title is not None:
        conditions.append(Alert.alert_title.ilike(f'%{title}%'))

    if description is not None:
        conditions.append(Alert.alert_description.ilike(f'%{description}%'))

    if status is not None:
        conditions.append(Alert.alert_status_id == status)

    if severity is not None:
        conditions.append(Alert.alert_severity_id == severity)

    if owner is not None:
        if owner == -1:
            conditions.append(Alert.alert_owner_id.is_(None))
        else:
            conditions.append(Alert.alert_owner_id == owner)

    if source is not None:
        conditions.append(Alert.alert_source.ilike(f'%{source}%'))

    if tags is not None:
        conditions.append(Alert.alert_tags.ilike(f"%{tags}%"))

    if client is not None:
        conditions.append(Alert.alert_customer_id == client)

    if alert_id is not None:
        conditions.append(Alert.alert_id == alert_id)

    if classification is not None:
        conditions.append(Alert.alert_classification_id == classification)

    if case_id is not None:
        conditions.append(Alert.cases.any(AlertCaseAssociation.case_id == case_id))

    if conditions:
        conditions = [and_(*conditions)] if len(conditions) > 1 else conditions
    else:
        conditions = []

    order_func = desc if sort == "desc" else asc

    try:

        # Query the alerts using the filter conditions
        filtered_alerts = db.session.query(
            Alert
        ).filter(
            *conditions
        ).options(
            joinedload(Alert.severity), joinedload(Alert.status), joinedload(Alert.customer), joinedload(Alert.cases),
            joinedload(Alert.iocs), joinedload(Alert.assets)
        ).order_by(
            order_func(Alert.alert_source_event_time)
        ).paginate(page, per_page, error_out=False)

    except Exception as e:
        app.app.logger.exception(f"Error getting alerts: {str(e)}")
        filtered_alerts = None

    return filtered_alerts


def add_alert(
        title,
        description,
        source,
        status,
        severity,
        owner
):
    """
    Add an alert to the database

    args:
        title (str): The title of the alert
        description (str): The description of the alert
        source (str): The source of the alert
        status (str): The status of the alert
        severity (str): The severity of the alert
        owner (str): The owner of the alert

    returns:
        Alert: The alert that was added to the database
    """
    # Create the alert
    alert = Alert()
    alert.alert_title = title
    alert.alert_description = description
    alert.alert_source = source
    alert.alert_status = status
    alert.alert_severity = severity
    alert.alert_owner_id = owner

    # Add the alert to the database
    db.session.add(alert)
    db.session.commit()

    return alert


def get_alert_by_id(alert_id: int) -> Alert:
    """
    Get an alert from the database

    args:
        alert_id (int): The ID of the alert

    returns:
        Alert: The alert that was retrieved from the database
    """
    return (
        db.session.query(Alert)
        .options(joinedload(Alert.iocs), joinedload(Alert.assets))
        .filter(Alert.alert_id == alert_id)
        .first()
    )


def get_unspecified_event_category():
    """
    Get the id of the 'Unspecified' event category
    """
    event_cat = EventCategory.query.filter(
        EventCategory.name == 'Unspecified'
    ).first()

    return event_cat


def create_case_from_alert(alert: Alert, iocs_list: List[str], assets_list: List[str],
                           note: str, import_as_event: bool, case_tags: str) -> Cases:
    """
    Create a case from an alert

    args:
        alert (Alert): The Alert
        iocs_list (list): The list of IOCs
        assets_list (list): The list of assets
        note (str): The note to add to the case
        import_as_event (bool): Whether to import the alert as an event
        case_tags (str): The tags to add to the case

    returns:
        Cases: The case that was created from the alert
    """

    escalation_note = ""
    if note:
        escalation_note = f"\n\n### Escalation note\n\n{note}\n\n"

    # Create the case
    case = Cases(
        name=f"[ALERT] {alert.alert_title}",
        description=f"*Alert escalated by {current_user.name}*\n\n{escalation_note}"
                    f"### Alert description\n\n{alert.alert_description}"
                    f"\n\n### IRIS alert link\n\n"
                    f"[<i class='fa-solid fa-bell'></i> #{alert.alert_id}](/alerts?alert_id={alert.alert_id})",
        soc_id=alert.alert_id,
        client_id=alert.alert_customer_id,
        user=current_user,
        classification_id=alert.alert_classification_id
    )

    case.save()

    for tag in case_tags.split(','):
        tag = Tags(tag_title=tag)
        tag = tag.save()
        case.tags.append(tag)

    db.session.commit()

    # Link the alert to the case
    alert.cases.append(case)

    ioc_schema = IocSchema()
    asset_schema = CaseAssetsSchema()
    ioc_links = []
    asset_links = []

    # Add the IOCs to the case
    for ioc_uuid in iocs_list:
        for alert_ioc in alert.alert_iocs:
            if alert_ioc['ioc_uuid'] == ioc_uuid:
                alert_ioc['ioc_tags'] = ','.join(alert_ioc['ioc_tags'])

                # TODO: Transform the ioc-enrichment to a custom attribute in the ioc
                del alert_ioc['ioc_enrichment']

                ioc = ioc_schema.load(alert_ioc, session=db.session)
                ioc, existed = add_ioc(ioc, current_user.id, case.case_id)
                add_ioc_link(ioc.ioc_id, case.case_id)
                ioc_links.append(ioc.ioc_id)

    # Add the assets to the case
    for asset_uuid in assets_list:
        for alert_asset in alert.alert_assets:
            if alert_asset['asset_uuid'] == asset_uuid:

                alert_asset['asset_tags'] = ','.join(alert_asset['asset_tags'])
                alert_asset['analysis_status_id'] = get_unspecified_analysis_status_id()

                # TODO: Transform the asset-enrichment to a custom attribute in the asset if possible
                del alert_asset['asset_enrichment']

                asset = asset_schema.load(alert_asset, session=db.session)

                asset = create_asset(asset=asset,
                                     caseid=case.case_id,
                                     user_id=current_user.id
                                     )
                set_ioc_links(ioc_links, asset.asset_id)
                asset_links.append(asset.asset_id)

    # Add event to timeline
    if import_as_event:

        unspecified_cat = get_unspecified_event_category()

        event_schema = EventSchema()
        event = event_schema.load({
            'event_title': f"[ALERT] {alert.alert_title}",
            'event_content': alert.alert_description,
            'event_source': alert.alert_source,
            'event_raw': json.dumps(alert.alert_source_content, indent=4),
            'event_date': alert.alert_source_event_time.strftime("%Y-%m-%dT%H:%M:%S.%f"),
            'event_date_wtz': alert.alert_source_event_time.strftime("%Y-%m-%dT%H:%M:%S.%f"),
            'event_iocs': ioc_links,
            'event_assets': asset_links,
            'event_tags': alert.alert_tags,
            'event_tz': '+00:00',
            'event_category_id': unspecified_cat.id,
        }, session=db.session)

        event.case_id = case.case_id
        event.user_id = current_user.id
        event.event_added = datetime.utcnow()

        add_obj_history_entry(event, 'created')

        db.session.add(event)
        update_timeline_state(caseid=case.case_id)

        event.category = [unspecified_cat]

        update_event_assets(event_id=event.event_id,
                            caseid=case.case_id,
                            assets_list=asset_links,
                            iocs_list=ioc_links,
                            sync_iocs_assets=False)

        update_event_iocs(event_id=event.event_id,
                          caseid=case.case_id,
                          iocs_list=ioc_links)

    db.session.commit()

    return case


def merge_alert_in_case(alert: Alert, case: Cases, iocs_list: List[str],
                        assets_list: List[str], note: str, import_as_event: bool, case_tags: str):
    """
    Merge an alert in a case

    args:
        alert (Alert): The Alert
        case (Cases): The Case
        iocs_list (list): The list of IOCs
        assets_list (list): The list of assets
        note (str): The note to add to the case
        import_as_event (bool): Whether to import the alert as an event
        case_tags (str): The tags to add to the case
    """
    if case in alert.cases:
        return case

    escalation_note = ""
    if note:
        escalation_note = f"\n\n### Escalation note\n\n{note}\n\n"

    case.description += f"\n\n*Alert #{alert.alert_id} escalated by {current_user.name}*\n\n{escalation_note}"

    for tag in case_tags.split(','):
        tag = Tags(tag_title=tag)
        tag.save()
        case.tags.append(tag)

    # Link the alert to the case
    alert.cases.append(case)

    ioc_schema = IocSchema()
    asset_schema = CaseAssetsSchema()
    ioc_links = []
    asset_links = []

    # Add the IOCs to the case
    for ioc_uuid in iocs_list:
        for alert_ioc in alert.alert_iocs:
            if alert_ioc['ioc_uuid'] == ioc_uuid:
                alert_ioc['ioc_tags'] = ','.join(alert_ioc['ioc_tags'])

                # TODO: Transform the ioc-enrichment to a custom attribute in the ioc
                del alert_ioc['ioc_enrichment']

                ioc = ioc_schema.load(alert_ioc, session=db.session)
                ioc, existed = add_ioc(ioc, current_user.id, case.case_id)
                add_ioc_link(ioc.ioc_id, case.case_id)
                ioc_links.append(ioc.ioc_id)

    # Add the assets to the case
    for asset_uuid in assets_list:
        for alert_asset in alert.alert_assets:
            if alert_asset['asset_uuid'] == asset_uuid:

                alert_asset['asset_tags'] = ','.join(alert_asset['asset_tags'])
                alert_asset['analysis_status_id'] = get_unspecified_analysis_status_id()

                # TODO: Transform the asset-enrichment to a custom attribute in the asset if possible
                del alert_asset['asset_enrichment']

                asset = asset_schema.load(alert_asset, session=db.session)

                asset = create_asset(asset=asset,
                                     caseid=case.case_id,
                                     user_id=current_user.id
                                     )
                set_ioc_links(ioc_links, asset.asset_id)
                asset_links.append(asset.asset_id)

    # Add event to timeline
    if import_as_event:
        unspecified_cat = get_unspecified_event_category()

        event_schema = EventSchema()
        event = event_schema.load({
            'event_title': f"[ALERT] {alert.alert_title}",
            'event_content': alert.alert_description,
            'event_source': alert.alert_source,
            'event_raw': json.dumps(alert.alert_source_content, indent=4),
            'event_date': alert.alert_source_event_time.strftime("%Y-%m-%dT%H:%M:%S.%f"),
            'event_date_wtz': alert.alert_source_event_time.strftime("%Y-%m-%dT%H:%M:%S.%f"),
            'event_iocs': ioc_links,
            'event_assets': asset_links,
            'event_tags': alert.alert_tags,
            'event_tz': '+00:00',
            'event_category_id': unspecified_cat.id,
        }, session=db.session)

        event.case_id = case.case_id
        event.user_id = current_user.id
        event.event_added = datetime.utcnow()

        add_obj_history_entry(event, 'created')

        db.session.add(event)
        update_timeline_state(caseid=case.case_id)

        event.category = [unspecified_cat]

        update_event_assets(event_id=event.event_id,
                            caseid=case.case_id,
                            assets_list=asset_links,
                            iocs_list=ioc_links,
                            sync_iocs_assets=False)

        update_event_iocs(event_id=event.event_id,
                          caseid=case.case_id,
                          iocs_list=ioc_links)

        db.session.commit()


def unmerge_alert_from_case(alert: Alert, case: Cases):
    """
    Unmerge an alert from a case

    args:
        alert (Alert): The Alert
        case (Cases): The Case
    """
    # Check if the case is in the alert.cases list
    if alert in case.alerts:
        # Unlink the alert from the case
        case.alerts.remove(alert)
        db.session.commit()
    else:
        return False, f"Case {case.case_id} not linked with alert {alert.alert_id}"

    return True, f"Alert {alert.alert_id} unlinked from case {case.case_id}"


def get_alert_status_list():
    """
    Get a list of alert statuses

    returns:
        list: A list of alert statuses
    """
    return db.session.query(AlertStatus).distinct().all()


def get_alert_status_by_id(status_id: int) -> AlertStatus:
    """
    Get an alert status from the database

    args:
        status_id (int): The ID of the alert status

    returns:
        AlertStatus: The alert status that was retrieved from the database
    """
    return db.session.query(AlertStatus).filter(AlertStatus.status_id == status_id).first()


def cache_similar_alert(customer_id, assets, iocs, alert_id):
    """
    Cache similar alerts

    args:
        customer_id (int): The ID of the customer
        assets (list): The list of assets
        iocs (list): The list of IOCs
        alert_id (int): The ID of the alert

    returns:
        None

    """
    for asset in assets:
        cache_entry = SimilarAlertsCache(customer_id=customer_id, asset_name=asset['asset_name'],
                                         asset_type_id=asset["asset_type_id"], alert_id=alert_id)
        db.session.add(cache_entry)

    for ioc in iocs:
        cache_entry = SimilarAlertsCache(customer_id=customer_id, ioc_value=ioc['ioc_value'],
                                         ioc_type_id=ioc['ioc_type_id'], alert_id=alert_id)
        db.session.add(cache_entry)

    db.session.commit()


def delete_similar_alert_cache(alert_id):
    """
    Delete the similar alert cache

    args:
        alert_id (int): The ID of the alert

    returns:
        None
    """
    SimilarAlertsCache.query.filter(SimilarAlertsCache.alert_id == alert_id).delete()
    db.session.commit()


def get_related_alerts(customer_id, assets, iocs, details=False):
    """
    Check if an alert is related to another alert

    args:
        customer_id (int): The ID of the customer
        assets (list): The list of assets
        iocs (list): The list of IOCs
        details (bool): Whether to return the details of the related alerts

    returns:
        bool: True if the alert is related to another alert, False otherwise
    """
    asset_names = [asset['asset_name'] for asset in assets]
    ioc_values = [ioc['ioc_value'] for ioc in iocs]

    similar_assets = SimilarAlertsCache.query.filter(
        SimilarAlertsCache.customer_id == customer_id,
        SimilarAlertsCache.asset_name.in_(asset_names)
    ).all()

    similar_iocs = SimilarAlertsCache.query.filter(
        SimilarAlertsCache.customer_id == customer_id,
        SimilarAlertsCache.ioc_value.in_(ioc_values)
    ).all()

    similarities = {
        'assets': [asset.alert_id for asset in similar_assets],
        'iocs': [ioc.alert_id for ioc in similar_iocs]
    }

    return similarities


def get_related_alerts_details(customer_id, assets, iocs):
    """
    Get the details of the related alerts

    args:
        customer_id (int): The ID of the customer
        assets (list): The list of assets
        iocs (list): The list of IOCs

    returns:
        dict: The details of the related alerts with matched assets and/or IOCs
    """
    if not assets or not iocs:
        return {
            'nodes': {},
            'edges': {}
        }

    asset_names = [asset.asset_name for asset in assets]
    ioc_values = [ioc.ioc_value for ioc in iocs]

    asset_type_alias = aliased(AssetsType)

    related_alerts = (
        db.session.query(Alert, SimilarAlertsCache.asset_name, SimilarAlertsCache.ioc_value,
                         asset_type_alias.asset_icon_not_compromised)
        .join(SimilarAlertsCache, Alert.alert_id == SimilarAlertsCache.alert_id)
        .outerjoin(asset_type_alias, SimilarAlertsCache.asset_type_id == asset_type_alias.asset_id)
        .filter(
            SimilarAlertsCache.customer_id == customer_id,
            (SimilarAlertsCache.asset_name.in_(asset_names) | SimilarAlertsCache.ioc_value.in_(ioc_values))
        )
        .all()
    )

    alerts_dict = {}

    for alert, asset_name, ioc_value, asset_icon_not_compromised in related_alerts:
        if alert.alert_id not in alerts_dict:
            alerts_dict[alert.alert_id] = {'alert': alert, 'assets': [], 'iocs': []}

        if asset_name in asset_names:
            asset_info = {'asset_name': asset_name, 'icon': asset_icon_not_compromised}
            alerts_dict[alert.alert_id]['assets'].append(asset_info)
        if ioc_value in ioc_values:
            alerts_dict[alert.alert_id]['iocs'].append(ioc_value)

    nodes = []
    edges = []

    added_assets = set()
    added_iocs = set()

    for alert_id, alert_info in alerts_dict.items():
        nodes.append({
            'id': f'alert_{alert_id}',
            'label': f'Alert #{alert_id}',
            'title': alert_info['alert'].alert_title,
            'group': 'alert',
            'shape': 'image',
            'image': '/static/assets/img/graph/bell-solid.png',
            'font': "12px verdana white" if current_user.in_dark_mode else ''
        })

        for asset_info in alert_info['assets']:
            asset_id = asset_info['asset_name']

            if asset_id not in added_assets:
                nodes.append({
                    'id': f'asset_{asset_id}',
                    'label': asset_id,
                    'group': 'asset',
                    'shape': 'image',
                    'image': '/static/assets/img/graph/' + asset_info['icon'],
                    'font': "12px verdana white" if current_user.in_dark_mode else ''
                })
                added_assets.add(asset_id)

            edges.append({
                'from': f'alert_{alert_id}',
                'to': f'asset_{asset_id}'
            })

        for ioc_value in alert_info['iocs']:
            if ioc_value not in added_iocs:
                nodes.append({
                    'id': f'ioc_{ioc_value}',
                    'label': ioc_value,
                    'group': 'ioc',
                    'shape': 'image',
                    'image': '/static/assets/img/graph/virus-covid-solid.png',
                    'font': "12px verdana white" if current_user.in_dark_mode else ''
                })
                added_iocs.add(ioc_value)

            edges.append({
                'from': f'alert_{alert_id}',
                'to': f'ioc_{ioc_value}',
                'dashes': True
            })

    return {
        'nodes': nodes,
        'edges': edges
    }


def get_alert_comments(alert_id: int) -> List[Comments]:
    """
    Get the comments of an alert

    args:
        alert_id (int): The ID of the alert

    returns:
        list: The list of comments
    """
    return Comments.query.filter(Comments.comment_alert_id == alert_id).all()


def get_alert_comment(alert_id: int, comment_id: int) -> Comments:
    """
    Get a comment of an alert

    args:
        alert_id (int): The ID of the alert
        comment_id (int): The ID of the comment

    returns:
        Comments: The comment
    """
    return Comments.query.filter(
        Comments.comment_alert_id == alert_id,
        Comments.comment_id == comment_id
    ).first()


def delete_alert_comment(comment_id: int, alert_id: int) -> Tuple[bool, str]:
    """
    Delete a comment of an alert

    args:
        comment_id (int): The ID of the comment
    """
    comment = Comments.query.filter(
        Comments.comment_id == comment_id,
        Comments.comment_user_id == current_user.id,
        Comments.comment_alert_id == alert_id
    ).first()
    if not comment:
        return False, "You are not allowed to delete this comment"

    db.session.delete(comment)
    db.session.commit()

    return True, "Comment deleted successfully"


def delete_alerts(alert_ids: List[int]) -> tuple[bool, str]:
    """
    Delete multiples alerts from the database

    args:
        alert_ids (List[int]): list of alerts to delete

    returns:
        True if deleted successfully
    """
    try:

        Comments.query.filter(Comments.comment_alert_id.in_(alert_ids)).delete()
        Alert.query.filter(Alert.alert_id.in_(alert_ids)).delete()

    except Exception as e:
        db.session.rollback()
        app.logger.exception(str(e))
        return False, str(e)

    return True, ""
