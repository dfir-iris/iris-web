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
from flask_login import current_user
from operator import and_
from sqlalchemy.orm import joinedload
from typing import List

from app import db
from app.datamgmt.case.case_assets_db import create_asset, set_ioc_links, get_unspecified_analysis_status_id
from app.datamgmt.case.case_iocs_db import add_ioc, add_ioc_link
from app.models import Cases
from app.models.alerts import Alert, AlertStatus
from app.schema.marshables import IocSchema, CaseAssetsSchema


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
        read: bool = None,
        client: int = None,
        classification: int = None,
        alert_id: int = None,
        page: int = 1,
        per_page: int = 10
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
        read (bool): The read status of the alert
        client (int): The client id of the alert
        classification (int): The classification id of the alert
        alert_id (int): The alert id
        page (int): The page number
        per_page (int): The number of alerts per page

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
        conditions.append(Alert.alert_owner_id == owner)

    if source is not None:
        conditions.append(Alert.alert_source.ilike(f'%{source}%'))

    if tags is not None:
        conditions.append(Alert.alert_tags.ilike(f"%{tags}%"))

    if read is not None:
        conditions.append(Alert.alert_is_read == read)

    if client is not None:
        conditions.append(Alert.alert_customer_id == client)

    if alert_id is not None:
        conditions.append(Alert.alert_id == alert_id)

    if classification is not None:
        conditions.append(Alert.alert_classification_id == classification)

    if conditions:
        conditions = [and_(*conditions)] if len(conditions) > 1 else conditions
    else:
        conditions = []

    # Query the alerts using the filter conditions
    filtered_alerts = db.session.query(
        Alert
    ).filter(
        *conditions
    ).options(
        joinedload(Alert.severity), joinedload(Alert.status), joinedload(Alert.customer)
    ).paginate(page, per_page, False)

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
    return db.session.query(Alert).filter(Alert.alert_id == alert_id).first()


def create_case_from_alert(alert: Alert, iocs_list: List[str], assets_list: List[str],
                           note: str, import_as_event: bool) -> Cases:
    """
    Create a case from an alert

    args:
        alert (Alert): The Alert
        iocs_list (list): The list of IOCs
        assets_list (list): The list of assets
        note (str): The note to add to the case
        import_as_event (bool): Whether to import the alert as an event

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
                    f"### Alert content\n\n{alert.alert_description}",
        soc_id=alert.alert_id,
        client_id=alert.alert_customer_id,
        user=current_user,
        classification_id=alert.alert_classification_id
    )

    case.save()

    # Link the alert to the case
    alert.cases.append(case)

    ioc_schema = IocSchema()
    asset_schema = CaseAssetsSchema()
    ioc_links = []

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

    db.session.commit()

    return case


def merge_alert_in_case(alert: Alert, case: Cases):
    """
    Merge an alert in a case

    args:
        alert (Alert): The Alert
        case (Cases): The Case
    """
    # Link the alert to the case
    alert.cases.append(case)

    db.session.commit()


def unmerge_alert_from_case(alert: Alert, case: Cases):
    """
    Unmerge an alert from a case

    args:
        alert (Alert): The Alert
        case (Cases): The Case
    """
    # Unlink the alert from the case
    alert.cases.remove(case)

    db.session.commit()


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
