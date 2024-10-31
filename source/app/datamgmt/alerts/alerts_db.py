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
from copy import deepcopy

import json
from datetime import datetime, timedelta
from flask_login import current_user
from functools import reduce
from operator import and_
from sqlalchemy import desc, asc, func, tuple_, or_
from sqlalchemy.orm import aliased, make_transient, selectinload
from typing import List, Tuple, Dict

import app
from app import db
from app.datamgmt.case.case_assets_db import create_asset, set_ioc_links, get_unspecified_analysis_status_id
from app.datamgmt.case.case_events_db import update_event_assets, update_event_iocs
from app.datamgmt.case.case_iocs_db import add_ioc, add_ioc_link
from app.datamgmt.manage.manage_access_control_db import get_user_clients_id
from app.datamgmt.manage.manage_case_state_db import get_case_state_by_name
from app.datamgmt.manage.manage_case_templates_db import get_case_template_by_id, \
    case_template_post_modifier
from app.datamgmt.states import update_timeline_state
from app.iris_engine.utils.common import parse_bf_date_format
from app.models import Cases, EventCategory, Tags, AssetsType, Comments, CaseAssets, alert_assets_association, \
    alert_iocs_association, Ioc, IocLink
from app.models.alerts import Alert, AlertStatus, AlertCaseAssociation, SimilarAlertsCache, AlertResolutionStatus, \
    AlertSimilarity
from app.schema.marshables import EventSchema, AlertSchema
from app.util import add_obj_history_entry


def db_list_all_alerts():
    """
    List all alerts in the database
    """
    return db.session.query(Alert).all()


def get_filtered_alerts(
        start_date: str = None,
        end_date: str = None,
        source_start_date: str = None,
        source_end_date: str = None,
        source_reference: str = None,
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
        alert_ids: List[int] = None,
        assets: List[str] = None,
        iocs: List[str] = None,
        resolution_status: int = None,
        page: int = 1,
        per_page: int = 10,
        sort: str = 'desc',
        current_user_id: int = None
):
    """
    Get a list of alerts that match the given filter conditions

    returns:
        dict: A dictionary containing the total count, alerts, and pagination information
    """
    # Build the filter conditions
    conditions = []

    if start_date is not None and end_date is not None:
        start_date = parse_bf_date_format(start_date)
        end_date = parse_bf_date_format(end_date)
        if start_date and end_date:
            conditions.append(Alert.alert_creation_time.between(start_date, end_date))

    if source_start_date is not None and source_end_date is not None:
        source_start_date = parse_bf_date_format(source_start_date)
        source_end_date = parse_bf_date_format(source_end_date)
        if source_start_date and source_end_date:
            conditions.append(Alert.alert_source_event_time.between(source_start_date, source_end_date))

    if title is not None:
        conditions.append(Alert.alert_title.ilike(f'%{title}%'))

    if description is not None:
        conditions.append(Alert.alert_description.ilike(f'%{description}%'))

    if status is not None:
        conditions.append(Alert.alert_status_id == status)

    if severity is not None:
        conditions.append(Alert.alert_severity_id == severity)

    if resolution_status is not None:
        conditions.append(Alert.alert_resolution_status_id == resolution_status)

    if source_reference is not None:
        conditions.append(Alert.alert_source_ref.like(f'%{source_reference}%'))

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

    if alert_ids is not None:
        if isinstance(alert_ids, list):
            conditions.append(Alert.alert_id.in_(alert_ids))

    if classification is not None:
        conditions.append(Alert.alert_classification_id == classification)

    if case_id is not None:
        conditions.append(Alert.cases.any(AlertCaseAssociation.case_id == case_id))

    if assets is not None:
        if isinstance(assets, list):
            conditions.append(Alert.assets.any(CaseAssets.asset_name.in_(assets)))

    if iocs is not None:
        if isinstance(iocs, list):
            conditions.append(Alert.iocs.any(Ioc.ioc_value.in_(iocs)))

    if current_user_id is not None:
        clients_filters = get_user_clients_id(current_user_id)
        if clients_filters is not None:
            conditions.append(Alert.alert_customer_id.in_(clients_filters))

    if len(conditions) > 1:
        conditions = [reduce(and_, conditions)]

    order_func = desc if sort == "desc" else asc

    alert_schema = AlertSchema()

    try:
        # Query the alerts using the filter conditions
        filtered_alerts = db.session.query(
            Alert
        ).filter(
            *conditions
        ).options(
            selectinload(Alert.severity), selectinload(Alert.status), selectinload(Alert.customer), selectinload(Alert.cases),
            selectinload(Alert.iocs), selectinload(Alert.assets)
        ).order_by(
            order_func(Alert.alert_source_event_time)
        ).paginate(page=page, per_page=per_page, error_out=False)

        return {
            'total': filtered_alerts.total,
            'alerts': alert_schema.dump(filtered_alerts, many=True),
            'last_page': filtered_alerts.pages,
            'current_page': filtered_alerts.page,
            'next_page': filtered_alerts.next_num if filtered_alerts.has_next else None,
        }

    except Exception as e:
        app.app.logger.exception(f"Error getting alerts: {str(e)}")
        return None


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
        .options(selectinload(Alert.iocs), selectinload(Alert.assets))
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


def create_case_from_alerts(alerts: List[Alert], iocs_list: List[str], assets_list: List[str], case_title: str,
                            note: str, import_as_event: bool, case_tags: str, template_id: int) -> Cases:
    """
    Create a case from multiple alerts

    args:
        alerts (Alert): The Alerts
        iocs_list (list): The list of IOCs
        assets_list (list): The list of assets
        note (str): The note to add to the case
        import_as_event (bool): Whether to import the alert as an event
        case_tags (str): The tags to add to the case
        case_title (str): The title of the case
        template_id (int): The ID of the template to use

    returns:
        Cases: The case that was created from the alert
    """

    escalation_note = ""
    if note:
        escalation_note = f"\n\n### Escalation note\n\n{note}\n\n"

    if template_id is not None and template_id != 0 and template_id != '':
        case_template = get_case_template_by_id(template_id)
        if case_template:
            case_template_title_prefix = case_template.title_prefix

    # Create the case
    case = Cases(
        name=f"[ALERT]{case_template_title_prefix} "
             f"Merge of alerts {', '.join([str(alert.alert_id) for alert in alerts])}" if not case_title else
             f"{case_template_title_prefix} {case_title}",
        description=f"*Alerts escalated by {current_user.name}*\n\n{escalation_note}"
                    f"[Alerts link](/alerts?alert_ids={','.join([str(alert.alert_id) for alert in alerts])})",
        soc_id='',
        client_id=alerts[0].alert_customer_id,
        user=current_user,
        classification_id=alerts[0].alert_classification_id,
        state_id=get_case_state_by_name('Open').state_id
    )

    case.save()

    for tag in case_tags.split(','):
        tag = Tags(tag_title=tag)
        tag = tag.save()
        case.tags.append(tag)

    db.session.commit()

    # Link the alert to the case
    for alert in alerts:
        alert.cases.append(case)

        ioc_links = []
        asset_links = []

        # Add the IOCs to the case
        for ioc_uuid in iocs_list:
            for alert_ioc in alert.iocs:
                if str(alert_ioc.ioc_uuid) == ioc_uuid:

                    ioc, existed = add_ioc(alert_ioc, current_user.id, case.case_id)
                    add_ioc_link(ioc.ioc_id, case.case_id)
                    ioc_links.append(ioc.ioc_id)

        # Add the assets to the case
        for asset_uuid in assets_list:
            for alert_asset in alert.assets:
                if str(alert_asset.asset_uuid) == asset_uuid:
                    alert_asset.analysis_status_id = get_unspecified_analysis_status_id()

                    asset = create_asset(asset=alert_asset,
                                         caseid=case.case_id,
                                         user_id=current_user.id
                                         )
                    asset.asset_uuid = alert_asset.asset_uuid

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

    if template_id is not None and template_id != 0 and template_id != '':
        case, logs = case_template_post_modifier(case, template_id)

    db.session.commit()

    return case


def create_case_from_alert(alert: Alert, iocs_list: List[str], assets_list: List[str], case_title: str,
                           note: str, import_as_event: bool, case_tags: str, template_id: int) -> Cases:
    """
    Create a case from an alert

    args:
        alert (Alert): The Alert
        iocs_list (list): The list of IOCs
        assets_list (list): The list of assets
        note (str): The note to add to the case
        import_as_event (bool): Whether to import the alert as an event
        case_tags (str): The tags to add to the case
        case_title (str): The title of the case
        template_id (int): The template to use for the case

    returns:
        Cases: The case that was created from the alert
    """

    escalation_note = ""
    if note:
        escalation_note = f"\n\n### Escalation note\n\n{note}\n\n"

    case_template_title_prefix = ""

    if template_id is not None and template_id != 0 and template_id != '':
        case_template = get_case_template_by_id(template_id)
        if case_template:
            case_template_title_prefix = case_template.title_prefix

    # Create the case
    case = Cases(
        name=f"[ALERT]{case_template_title_prefix} {alert.alert_title}" if not case_title else f"{case_template_title_prefix} {case_title}",
        description=f"*Alert escalated by {current_user.name}*\n\n{escalation_note}"
                    f"### Alert description\n\n{alert.alert_description}"
                    f"\n\n### IRIS alert link\n\n"
                    f"[<i class='fa-solid fa-bell'></i> #{alert.alert_id}](/alerts?alert_ids={alert.alert_id})",
        soc_id=alert.alert_id,
        client_id=alert.alert_customer_id,
        user=current_user,
        classification_id=alert.alert_classification_id,
        state_id=get_case_state_by_name('Open').state_id
    )

    case.save()

    for tag in case_tags.split(','):
        tag = Tags(tag_title=tag)
        tag = tag.save()
        case.tags.append(tag)

    case.severity_id = alert.alert_severity_id

    db.session.commit()

    # Link the alert to the case
    alert.cases.append(case)

    ioc_links = []
    asset_links = []

    # Add the IOCs to the case
    for ioc_uuid in iocs_list:
        for alert_ioc in alert.iocs:
            if str(alert_ioc.ioc_uuid) == ioc_uuid:

                ioc, existed = add_ioc(alert_ioc, current_user.id, case.case_id)
                add_ioc_link(ioc.ioc_id, case.case_id)
                ioc_links.append(ioc.ioc_id)

    # Add the assets to the case
    for asset_uuid in assets_list:
        for alert_asset in alert.assets:
            if str(alert_asset.asset_uuid) == asset_uuid:
                alert_asset.analysis_status_id = get_unspecified_analysis_status_id()

                if alert_asset.case_id is not None:
                    # Make a deep copy of the asset
                    # prevent the asset to conflict with the existing asset
                    new_alert_asset = deepcopy(alert_asset)
                    make_transient(new_alert_asset)

                    new_alert_asset.asset_id = None
                    new_alert_asset.asset_uuid = asset_uuid

                    db.session.add(new_alert_asset)
                    db.session.commit()

                asset = create_asset(asset=alert_asset,
                                     caseid=case.case_id,
                                     user_id=current_user.id
                                     )
                asset.asset_uuid = alert_asset.asset_uuid

                set_ioc_links(ioc_links, asset.asset_id)
                asset_links.append(asset.asset_id)

    # Add event to timeline
    if import_as_event:
        unspecified_cat = get_unspecified_event_category()

        event_schema = EventSchema()
        event = event_schema.load({
            'event_title': f"[ALERT] {alert.alert_title}",
            'event_content': alert.alert_description if alert.alert_description else "",
            'event_source': alert.alert_source if alert.alert_source else "",
            'event_raw': json.dumps(alert.alert_source_content, indent=4) if alert.alert_source_content else "",
            'event_date': alert.alert_source_event_time.strftime("%Y-%m-%dT%H:%M:%S.%f") if alert.alert_source_event_time else datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"),
            'event_date_wtz': alert.alert_source_event_time.strftime("%Y-%m-%dT%H:%M:%S.%f") if alert.alert_source_event_time else datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"),
            'event_iocs': ioc_links,
            'event_assets': asset_links,
            'event_tags': alert.alert_tags + ',alert' if alert.alert_tags else "alert",
            'event_tz': '+00:00',
            'event_category_id': unspecified_cat.id,
            'event_in_graph': True,
            'event_in_summary': True
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

    if template_id is not None and template_id != 0 and template_id != '':
        case, logs = case_template_post_modifier(case, template_id)

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
        case_title (str): The title of the case
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

    case.description += f"\n\n*Alert [#{alert.alert_id}](/alerts?alert_ids={alert.alert_id}) escalated by {current_user.name}*\n\n{escalation_note}"

    for tag in case_tags.split(',') if case_tags else []:
        tag = Tags(tag_title=tag).save()
        case.tags.append(tag)

    # Link the alert to the case
    alert.cases.append(case)

    ioc_links = []
    asset_links = []

    # Add the IOCs to the case
    for ioc_uuid in iocs_list:
        for alert_ioc in alert.iocs:
            if str(alert_ioc.ioc_uuid) == ioc_uuid:

                ioc, existed = add_ioc(alert_ioc, current_user.id, case.case_id)
                add_ioc_link(ioc.ioc_id, case.case_id)
                ioc_links.append(ioc.ioc_id)

    # Add the assets to the case
    for asset_uuid in assets_list:
        for alert_asset in alert.assets:
            if str(alert_asset.asset_uuid) == asset_uuid:

                alert_asset.analysis_status_id = get_unspecified_analysis_status_id()

                tmp_asset = CaseAssets.query.filter(
                    CaseAssets.asset_uuid == alert_asset.asset_uuid,
                    CaseAssets.case_id == case.case_id
                ).first()

                if tmp_asset:
                    asset = tmp_asset
                else:
                    asset = create_asset(asset=alert_asset,
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
            'event_in_graph': True,
            'event_in_summary': True
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
    if case in alert.cases:
        # Unlink the alert from the case
        alert.cases.remove(case)
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


def search_alert_status_by_name(status_name: str, exact_match: False) -> AlertStatus:
    """
    Get an alert status from the database from its name

    args:
        status_name (str): The name of the alert status
        exact_match (bool): Whether to perform an exact match or not

    returns:
        AlertStatus: The alert status that was retrieved from the database
    """
    if exact_match:
        return db.session.query(AlertStatus).filter(func.lower(AlertStatus.status_name) == status_name.lower()).first()

    return db.session.query(AlertStatus).filter(AlertStatus.status_name.ilike(f"%{status_name}%")).all()


def get_alert_resolution_list():
    """
    Get a list of alert resolutions

    returns:
        list: A list of alert resolutions
    """
    return db.session.query(AlertResolutionStatus).distinct().all()


def get_alert_resolution_by_id(resolution_id: int) -> AlertResolutionStatus:
    """
    Get an alert resolution from the database

    args:
        resolution_id (int): The ID of the alert resolution

    returns:
        Alertresolution: The alert resolution that was retrieved from the database
    """
    return db.session.query(AlertResolutionStatus).filter(AlertResolutionStatus.resolution_status_id == resolution_id).first()


def search_alert_resolution_by_name(resolution_status_name: str, exact_match: False) -> AlertResolutionStatus:
    """
    Get an alert resolution from the database from its name

    args:
        resolution_name (str): The name of the alert resolution
        exact_match (bool): Whether to perform an exact match or not

    returns:
        Alertresolution: The alert resolution that was retrieved from the database
    """
    if exact_match:
        return db.session.query(AlertResolutionStatus).filter(func.lower(
            AlertResolutionStatus.resolution_status_name) == resolution_status_name.lower()).first()

    return db.session.query(AlertResolutionStatus).filter(
        AlertResolutionStatus.resolution_status_name.ilike(f"%{resolution_status_name}%")).all()


def cache_similar_alert(customer_id, assets, iocs, alert_id, creation_date):
    """
    Cache similar alerts

    args:
        customer_id (int): The ID of the customer
        assets (list): The list of assets
        iocs (list): The list of IOCs
        alert_id (int): The ID of the alert
        creation_date (datetime): The creation date of the alert

    returns:
        None

    """
    for asset in assets:
        cache_entry = SimilarAlertsCache(customer_id=customer_id, asset_name=asset['asset_name'],
                                         asset_type_id=asset["asset_type_id"], alert_id=alert_id,
                                         created_at=creation_date)
        db.session.add(cache_entry)

    for ioc in iocs:
        cache_entry = SimilarAlertsCache(customer_id=customer_id, ioc_value=ioc['ioc_value'],
                                         ioc_type_id=ioc['ioc_type_id'], alert_id=alert_id,
                                         created_at=creation_date)
        db.session.add(cache_entry)

    db.session.commit()


def register_related_alerts(new_alert=None, assets_list=None, iocs_list=None):
    """
    Register related alerts
    """


    # Step 1: Identify similar alerts based on title, assets, and IOCs
    similar_alerts = db.session.query(Alert).filter(
        Alert.alert_customer_id == new_alert.alert_customer_id,
        Alert.alert_id != new_alert.alert_id,
        or_(
            Alert.alert_title == new_alert.alert_title,
            Alert.assets.any(CaseAssets.asset_name.in_([asset.asset_name for asset in new_alert.assets])),
            Alert.iocs.any(Ioc.ioc_value.in_([ioc.ioc_value for ioc in new_alert.iocs]))
        )
    ).all()

    # Step 2: Create relationships in the AlertSimilarity table
    for similar_alert in similar_alerts:
        # Matching on title
        if new_alert.alert_title == similar_alert.alert_title:
            alert_similarity = AlertSimilarity(
                alert_id=new_alert.alert_id,
                similar_alert_id=similar_alert.alert_id,
                similarity_type="title_match"
            )
            db.session.add(alert_similarity)

        # Matching on assets
        for asset in new_alert.assets:
            if asset in similar_alert.assets:
                alert_similarity = AlertSimilarity(
                    alert_id=new_alert.alert_id,
                    similar_alert_id=similar_alert.alert_id,
                    similarity_type="asset_match",
                    matching_asset_id=asset.asset_id
                )
                db.session.add(alert_similarity)

        # Matching on IOCs
        for ioc in new_alert.iocs:
            if ioc in similar_alert.iocs:
                alert_similarity = AlertSimilarity(
                    alert_id=new_alert.alert_id,
                    similar_alert_id=similar_alert.alert_id,
                    similarity_type="ioc_match",
                    matching_ioc_id=ioc.ioc_id
                )
                db.session.add(alert_similarity)


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


def delete_related_alerts_cache(alert_id):
    """
    Delete the related alerts cache

    args:
        alert_id (int): The ID of the alert

    returns:
        None
    """
    AlertSimilarity.query.filter(
        or_(
            AlertSimilarity.alert_id == alert_id,
            AlertSimilarity.similar_alert_id == alert_id
        )
    ).delete()
    db.session.commit()

def delete_similar_alerts_cache(alert_ids: List[int]):
    """
    Delete the similar alerts cache

    args:
        alert_ids (List(int)): The ID of the alert

    returns:
        None
    """
    SimilarAlertsCache.query.filter(SimilarAlertsCache.alert_id.in_(alert_ids)).delete()
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
    asset_names = [asset.asset_name for asset in assets]
    ioc_values = [ioc.ioc_value for ioc in iocs]

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


def get_related_alerts_details(customer_id, assets, iocs, open_alerts, closed_alerts, open_cases, closed_cases,
                               days_back=30, number_of_results=200):
    """
    Get the details of the related alerts

    args:
        customer_id (int): The ID of the customer
        assets (list): The list of assets
        iocs (list): The list of IOCs
        open_alerts (bool): Include open alerts
        closed_alerts (bool): Include closed alerts
        open_cases (bool): Include open cases
        closed_cases (bool): Include closed cases
        days_back (int): The number of days to look back
        number_of_results (int): The maximum number of alerts to return

    returns:
        dict: The details of the related alerts with matched assets and/or IOCs
    """
    if not assets and not iocs:
        return {
            'nodes': [],
            'edges': []
        }

    asset_names = [(asset.asset_name, asset.asset_type_id) for asset in assets]
    ioc_values = [(ioc.ioc_value, ioc.ioc_type_id) for ioc in iocs]

    asset_type_alias = aliased(AssetsType)
    alert_status_filter = []

    if open_alerts:
        open_alert_status_ids = AlertStatus.query.with_entities(
            AlertStatus.status_id
        ).filter(AlertStatus.status_name.in_(['New', 'Assigned', 'In progress', 'Pending', 'Unspecified'])).all()
        alert_status_filter += [status_id[0] for status_id in open_alert_status_ids]

    if closed_alerts:
        closed_alert_status_ids = AlertStatus.query.with_entities(
            AlertStatus.status_id
        ).filter(AlertStatus.status_name.in_(['Closed', 'Merged', 'Escalated'])).all()
        alert_status_filter += [status_id[0] for status_id in closed_alert_status_ids]

    conditions = and_(
        SimilarAlertsCache.customer_id == customer_id,
        and_(or_(
            tuple_(SimilarAlertsCache.asset_name, SimilarAlertsCache.asset_type_id).in_(asset_names),
            tuple_(SimilarAlertsCache.ioc_value, SimilarAlertsCache.ioc_type_id).in_(ioc_values)
        ),
        SimilarAlertsCache.created_at >= (func.now() - timedelta(days=days_back))
        )
    )

    if alert_status_filter:
        conditions = and_(conditions, Alert.alert_status_id.in_(alert_status_filter))

    related_alerts = (
        db.session.query(Alert, SimilarAlertsCache.asset_name, SimilarAlertsCache.ioc_value,
                         asset_type_alias.asset_icon_not_compromised)
        .join(SimilarAlertsCache, Alert.alert_id == SimilarAlertsCache.alert_id)
        .outerjoin(Alert.resolution_status)
        .outerjoin(asset_type_alias, SimilarAlertsCache.asset_type_id == asset_type_alias.asset_id)
        .filter(conditions)
        .limit(number_of_results)
        .all()
    )

    alerts_dict = {}

    for alert, asset_name, ioc_value, asset_icon_not_compromised in related_alerts:
        if alert.alert_id not in alerts_dict:
            alerts_dict[alert.alert_id] = {'alert': alert, 'assets': [], 'iocs': []}

        if any(name == asset_name for name, _ in asset_names):
            asset_info = {'asset_name': asset_name, 'icon': asset_icon_not_compromised}
            alerts_dict[alert.alert_id]['assets'].append(asset_info)

        if any(value == ioc_value for value, _ in ioc_values):
            alerts_dict[alert.alert_id]['iocs'].append(ioc_value)

    nodes = []
    edges = []

    added_assets = set()
    added_iocs = set()
    added_cases = set()

    for alert_id, alert_info in alerts_dict.items():
        alert_color = '#c95029' if alert_info['alert'].status.status_name in ['Closed', 'Merged', 'Escalated'] else ''

        alert_resolution_title = f'[{alert_info["alert"].resolution_status.resolution_status_name}]\n' if alert_info["alert"].resolution_status else ""

        nodes.append({
            'id': f'alert_{alert_id}',
            'label': f'[Closed]{alert_resolution_title} {alert_info["alert"].alert_title}' if alert_color != '' else f'{alert_resolution_title}{alert_info["alert"].alert_title}',
            'title': f'{alert_info["alert"].alert_description}',
            'group': 'alert',
            'shape': 'icon',
            'icon': {
                'face': 'FontAwesome',
                'code': '\uf0f3',
                'color': alert_color,
                'weight': "bold"
            },
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
                    'shape': 'icon',
                    'icon': {
                        'face': 'FontAwesome',
                        'code': '\ue4a8',
                        'color': 'white' if current_user.in_dark_mode else '',
                        'weight': "bold"
                    },
                    'font': "12px verdana white" if current_user.in_dark_mode else ''
                })
                added_iocs.add(ioc_value)

            edges.append({
                'from': f'alert_{alert_id}',
                'to': f'ioc_{ioc_value}',
                'dashes': True
            })

    if open_cases or closed_cases:
        close_condition = None
        if open_cases and not closed_cases:
            close_condition = Cases.close_date.is_(None)
        if closed_cases and not open_cases:
            close_condition = Cases.close_date.isnot(None)
        if open_cases and closed_cases:
            close_condition = Cases.close_date.isnot(None) | Cases.close_date.is_(None)

        matching_ioc_cases = (
            db.session.query(IocLink)
            .with_entities(IocLink.case_id, Ioc.ioc_value, Cases.name, Cases.close_date, Cases.description)
            .join(IocLink.ioc)
            .join(IocLink.case)
            .filter(
                and_(
                    and_(
                        Ioc.ioc_value.in_(added_iocs),
                        close_condition,
                    ),
                    Cases.client_id == customer_id
                )
            )
            .distinct()
            .all()
        )

        matching_asset_cases = (
            db.session.query(CaseAssets)
            .with_entities(CaseAssets.case_id, CaseAssets.asset_name, Cases.name, Cases.close_date, Cases.description)
            .join(CaseAssets.case)
            .filter(
                and_(
                    and_(
                        CaseAssets.asset_name.in_(added_assets),
                        close_condition
                    ),
                    Cases.client_id == customer_id
                )
            )
            .distinct(CaseAssets.case_id)
            .all()
        )

        cases_data = {}

        for case_id, ioc_value, case_name, close_date, case_desc in matching_ioc_cases:
            if case_id not in cases_data:
                cases_data[case_id] = {'name': case_name, 'matching_ioc': [], 'matching_assets': [],
                                       'close_date': close_date, 'description': case_desc}
            cases_data[case_id]['matching_ioc'].append(ioc_value)

        for case_id, asset_name, case_name, close_date, case_desc in matching_asset_cases:
            if case_id not in cases_data:
                cases_data[case_id] = {'name': case_name, 'matching_ioc': [], 'matching_assets': [],
                                       'close_date': close_date, 'description': case_desc}
            cases_data[case_id]['matching_assets'].append(asset_name)

        for case_id in cases_data:
            if case_id not in added_cases:
                nodes.append({
                    'id': f'case_{case_id}',
                    'label': f'[Closed] Case #{case_id}' if cases_data[case_id].get('close_date') else f'Case #{case_id}',
                    'title': cases_data[case_id].get("description"),
                    'group': 'case',
                    'shape': 'icon',
                    'icon': {
                        'face': 'FontAwesome',
                        'code': '\uf0b1',
                        'color': '#c95029' if cases_data[case_id].get('close_date') else '#4cba4f'
                    },
                    'font': "12px verdana white" if current_user.in_dark_mode else ''
                })
                added_cases.add(case_id)

            for ioc_value in cases_data[case_id]['matching_ioc']:
                edges.append({
                    'from': f'ioc_{ioc_value}',
                    'to': f'case_{case_id}',
                    'dashes': True
                })

            for asset_name in cases_data[case_id]['matching_assets']:
                edges.append({
                    'from': f'asset_{asset_name}',
                    'to': f'case_{case_id}',
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


def remove_alerts_from_assets_by_ids(alert_ids: List[int]) -> None:
    """
    Remove the alerts from the CaseAssets based on the alert_ids

    args:
        alert_ids (List[int]): list of alerts to remove

    returns:
        None
    """
    # Query the affected CaseAssets based on the alert_ids
    affected_case_assets = (
        db.session.query(CaseAssets)
        .join(alert_assets_association)
        .join(Alert, alert_assets_association.c.alert_id == Alert.alert_id)
        .filter(Alert.alert_id.in_(alert_ids))
        .all()
    )

    # Remove the alerts and delete the CaseAssets if not related to a case
    for case_asset in affected_case_assets:
        # Remove the alerts based on alert_ids
        case_asset.alerts = [alert for alert in case_asset.alerts if alert.alert_id not in alert_ids]

        # Delete the CaseAsset if it's not related to a case
        if case_asset.case_id is None:
            db.session.delete(case_asset)

    # Commit the changes
    db.session.commit()


def remove_alerts_from_iocs_by_ids(alert_ids: List[int]) -> None:
    """
    Remove the alerts from the Ioc based on the alert_ids

    args:
        alert_ids (List[int]): list of alerts to remove

    returns:
        None
    """
    # Query the affected CaseAssets based on the alert_ids
    affected_case_iocs = (
        db.session.query(Ioc)
        .join(alert_iocs_association)
        .join(Alert, alert_iocs_association.c.alert_id == Alert.alert_id)
        .filter(Alert.alert_id.in_(alert_ids))
        .all()
    )

    # Remove the alerts and delete the Ioc if not related to a case
    for ioc in affected_case_iocs:
        # Remove the alerts based on alert_ids
        ioc.alerts = [alert for alert in ioc.alerts if alert.alert_id not in alert_ids]

    # Commit the changes
    db.session.commit()


def remove_case_alerts_by_ids(alert_ids: List[int]) -> None:
    """
    Remove the alerts from the Case based on the alert_ids

    args:
        alert_ids (List[int]): list of alerts to remove

    returns:
        None
    """
    affected_cases = (
        db.session.query(Cases)
        .join(AlertCaseAssociation)
        .join(Alert, AlertCaseAssociation.alert_id == Alert.alert_id)
        .filter(Alert.alert_id.in_(alert_ids))
        .all()
    )

    for case in affected_cases:
        # Remove the alerts based on alert_ids
        case.alerts = [alert for alert in case.alerts if alert.alert_id not in alert_ids]

    db.session.query(AlertCaseAssociation).filter(
        AlertCaseAssociation.alert_id.in_(alert_ids)
    ).delete(synchronize_session='fetch')

    db.session.commit()


def delete_alerts(alert_ids: List[int]) -> tuple[bool, str]:
    """
    Delete multiples alerts from the database

    args:
        alert_ids (List[int]): list of alerts to delete

    returns:
        True if deleted successfully
    """
    try:

        delete_similar_alerts_cache(alert_ids)

        remove_alerts_from_assets_by_ids(alert_ids)
        remove_alerts_from_iocs_by_ids(alert_ids)
        remove_case_alerts_by_ids(alert_ids)

        Comments.query.filter(Comments.comment_alert_id.in_(alert_ids)).delete()
        Alert.query.filter(Alert.alert_id.in_(alert_ids)).delete()

    except Exception as e:
        db.session.rollback()
        app.logger.exception(str(e))
        return False, "Server side error"

    return True, ""


def get_alert_status_by_name(name: str) -> AlertStatus:
    """
    Get the alert status by name

    args:
        name (str): The name of the alert status

    returns:
        AlertStatus: The alert status
    """
    return AlertStatus.query.filter(AlertStatus.status_name == name).first()

