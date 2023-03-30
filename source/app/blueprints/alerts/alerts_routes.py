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
from datetime import datetime

from flask import Blueprint, request
from flask_login import current_user
from werkzeug import Response

from app import db
from app.datamgmt.alerts.alerts_db import get_filtered_alerts, get_alert_by_id
from app.models.authorization import Permissions
from app.schema.marshables import AlertSchema
from app.util import ac_api_requires, response_error, str_to_bool
from app.util import response_success

alerts_blueprint = Blueprint(
    'alerts',
    __name__,
    template_folder='templates'
)


# CONTENT ------------------------------------------------
@alerts_blueprint.route('/alerts/filter', methods=['GET'])
@ac_api_requires(Permissions.alerts_reader)
def alerts_list_route(caseid) -> Response:
    """
    Get a list of alerts from the database

    args:
        caseid (str): The case id

    returns:
        Response: The response
    """

    alert_schema = AlertSchema()

    alert_is_read_str = request.args.get('alert_is_read')
    alert_is_read = str_to_bool(alert_is_read_str) if alert_is_read_str is not None else None

    filtered_data = get_filtered_alerts(
        start_date=request.args.get('source_start_date'),
        end_date=request.args.get('source_end_date'),
        title=request.args.get('alert_title'),
        description=request.args.get('alert_description'),
        status=request.args.get('alert_status_id'),
        severity=request.args.get('alert_severity_id'),
        owner=request.args.get('alert_owner_id'),
        source=request.args.get('alert_source'),
        tags=request.args.get('alert_tags'),
        read=alert_is_read
    )

    return response_success(data=alert_schema.dump(filtered_data, many=True))


@alerts_blueprint.route('/alerts/add', methods=['POST'])
@ac_api_requires(Permissions.alerts_writer)
def alerts_add_route(caseid) -> Response:
    """
    Add a new alert to the database

    args:
        caseid (str): The case id

    returns:
        Response: The response
    """

    if not request.json:
        return response_error('No JSON data provided')

    alert_schema = AlertSchema()

    try:
        # Load the JSON data from the request
        data = request.get_json()

        # Deserialize the JSON data into an Alert object
        new_alert = alert_schema.load(data)

        new_alert.alert_owner_id = current_user.id
        new_alert.alert_creation_time = datetime.utcnow()

        # Add the new alert to the session and commit it
        db.session.add(new_alert)
        db.session.commit()

        # Return the newly created alert as JSON
        return response_success(data=alert_schema.dump(new_alert))

    except Exception as e:
        # Handle any errors during deserialization or DB operations
        return response_error(str(e))


@alerts_blueprint.route('/alerts/<int:alert_id>', methods=['GET'])
@ac_api_requires(Permissions.alerts_reader)
def alerts_get_route(caseid, alert_id) -> Response:
    """
    Get an alert from the database

    args:
        caseid (str): The case id
        alert_id (int): The alert id

    returns:
        Response: The response
    """

    alert_schema = AlertSchema()

    # Get the alert from the database
    alert = get_alert_by_id(alert_id)

    # Return the alert as JSON
    if alert is None:
        return response_error('Alert not found')

    return response_success(data=alert_schema.dump(alert))

