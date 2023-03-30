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

from app import db
from app.models import Cases
from app.models.alerts import Alert


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
        status: str = None,
        severity: str = None,
        owner: str = None,
        source: str = None,
        tags: str = None,
        read: bool = None,
        client: int = None,
        classification: int = None
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

    returns:
        list: A list of alerts that match the given filter conditions
    """
    # Build the filter conditions
    conditions = []

    if start_date and end_date:
        conditions.append(Alert.alert_creation_time.between(start_date, end_date))

    if title:
        conditions.append(Alert.alert_title.ilike(f'%{title}%'))

    if description:
        conditions.append(Alert.alert_description.ilike(f'%{description}%'))

    if status:
        conditions.append(Alert.alert_status_id == status)

    if severity:
        conditions.append(Alert.alert_severity_id == severity)

    if owner:
        conditions.append(Alert.alert_owner_id == owner)

    if source:
        conditions.append(Alert.alert_source == source)

    if tags:
        conditions.append(Alert.alert_tags.ilike(f"%{tags}%"))

    if read is not None:
        conditions.append(Alert.alert_is_read == read)

    if client:
        conditions.append(Alert.alert_client_id == client)

    if classification:
        conditions.append(Alert.alert_classification_id == classification)

    if conditions:
        conditions = [and_(*conditions)] if len(conditions) > 1 else conditions
    else:
        conditions = []

    # Query the alerts using the filter conditions
    filtered_alerts = db.session.query(Alert).filter(*conditions).all()

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


def create_case_from_alert(alert: Alert) -> Cases:
    """
    Create a case from an alert

    args:
        alert (Alert): The Alert

    returns:
        Cases: The case that was created from the alert
    """
    # Create the case
    case = Cases(
        name=f"[ALERT] {alert.alert_title}",
        description=f"*Alert escalated by {current_user.name}*\n\n### Alert content\n\n{alert.alert_description}",
        soc_id=alert.alert_id,
        client_id=alert.alert_client_id,
        user=current_user,
        classification_id=alert.alert_classification_id
    )

    case.save()

    # Link the alert to the case
    alert.cases.append(case)

    db.session.commit()

    return case
