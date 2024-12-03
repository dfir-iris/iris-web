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

from flask import Blueprint, request, Response
from flask_login import current_user

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_success, response_api_error
from app.blueprints.rest.parsing import parse_comma_separated_identifiers
from app.datamgmt.alerts.alerts_db import get_filtered_alerts
from app.models.authorization import Permissions

api_v2_alerts_blueprint = Blueprint('alert_rest_v2',
                                    __name__,
                                    url_prefix='/api/v2')


@api_v2_alerts_blueprint.route('/alerts/filter', methods=['GET'])
@ac_api_requires(Permissions.alerts_read)
def alerts_list_route() -> Response:
    """
    Get a list of alerts from the database

    args:
        caseid (str): The case id

    returns:
        Response: The response
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    alert_ids_str = request.args.get('alert_ids')
    alert_ids = None
    if alert_ids_str:
        try:

            alert_ids = parse_comma_separated_identifiers(alert_ids_str)

        except ValueError:
            return response_api_error('Invalid alert id')

    alert_assets_str = request.args.get('alert_assets')
    alert_assets = None
    if alert_assets_str:
        try:
            alert_assets = [str(alert_asset) for alert_asset in alert_assets_str.split(',')]

        except ValueError:
            return response_api_error('Invalid alert asset')

    alert_iocs_str = request.args.get('alert_iocs')
    alert_iocs = None
    if alert_iocs_str:
        try:
            alert_iocs = [str(alert_ioc) for alert_ioc in alert_iocs_str.split(',')]

        except ValueError:
            return response_api_error('Invalid alert ioc')

    filtered_data = get_filtered_alerts(
        start_date=request.args.get('creation_start_date'),
        end_date=request.args.get('creation_end_date'),
        source_start_date=request.args.get('source_start_date'),
        source_end_date=request.args.get('source_end_date'),
        source_reference=request.args.get('source_reference'),
        title=request.args.get('alert_title'),
        description=request.args.get('alert_description'),
        status=request.args.get('alert_status_id', type=int),
        severity=request.args.get('alert_severity_id', type=int),
        owner=request.args.get('alert_owner_id', type=int),
        source=request.args.get('alert_source'),
        tags=request.args.get('alert_tags'),
        classification=request.args.get('alert_classification_id', type=int),
        client=request.args.get('alert_customer_id'),
        case_id=request.args.get('case_id', type=int),
        alert_ids=alert_ids,
        page=page,
        per_page=per_page,
        sort=request.args.get('sort'),
        custom_conditions=request.args.get('custom_conditions'),
        assets=alert_assets,
        iocs=alert_iocs,
        resolution_status=request.args.get('alert_resolution_id', type=int),
        current_user_id=current_user.id
    )

    if filtered_data is None:
        return response_api_error('Filtering error')

    return response_api_success(data=filtered_data)