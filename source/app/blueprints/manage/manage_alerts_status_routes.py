#  IRIS Source Code
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

from flask import Blueprint, Response, request

from app.datamgmt.alerts.alerts_db import get_alert_status_list
from app.datamgmt.alerts.alerts_db import get_alert_status_by_id
from app.datamgmt.alerts.alerts_db import search_alert_status_by_name
from app.datamgmt.alerts.alerts_db import get_alert_resolution_by_id
from app.datamgmt.alerts.alerts_db import get_alert_resolution_list
from app.datamgmt.alerts.alerts_db import search_alert_resolution_by_name
from app.schema.marshables import AlertStatusSchema
from app.schema.marshables import AlertResolutionSchema
from app.util import ac_api_requires
from app.util import response_error
from app.util import response_success

manage_alerts_status_blueprint = Blueprint('manage_alerts_status',
                                           __name__,
                                           template_folder='templates')


# CONTENT ------------------------------------------------
@manage_alerts_status_blueprint.route('/manage/alert-status/list', methods=['GET'])
@ac_api_requires()
def list_alert_status() -> Response:
    """
    Get the list of alert status

    Args:
        caseid (int): case id

    Returns:
        Flask Response object
    """
    l_cl = get_alert_status_list()
    schema = AlertStatusSchema()

    return response_success("", data=schema.dump(l_cl, many=True))


@manage_alerts_status_blueprint.route('/manage/alert-status/<int:classification_id>', methods=['GET'])
@ac_api_requires()
def get_case_alert_status(classification_id: int) -> Response:
    """
    Get the alert status

    Args:
        status_id (int): status id
        caseid (int): case id
    """
    cl = get_alert_status_by_id(classification_id)
    schema = AlertStatusSchema()

    return response_success("", data=schema.dump(cl))


@manage_alerts_status_blueprint.route('/manage/alert-status/search', methods=['POST'])
@ac_api_requires()
def search_alert_status():
    if not request.is_json:
        return response_error("Invalid request")

    alert_status = request.json.get('alert_status')
    if alert_status is None:
        return response_error("Invalid alert status. Got None")

    exact_match = request.json.get('exact_match', False)

    # Search for alerts status with a name that contains the specified search term
    alert_status = search_alert_status_by_name(alert_status, exact_match=exact_match)
    if not alert_status:
        return response_error("No alert status found")

    # Serialize the alert status and return them in a JSON response
    schema = AlertStatusSchema(many=True)
    return response_success("", data=schema.dump(alert_status))


@manage_alerts_status_blueprint.route('/manage/alert-resolutions/list', methods=['GET'])
@ac_api_requires()
def list_alert_resolution() -> Response:
    """
    Get the list of alert resolution

    Args:
        caseid (int): case id

    Returns:
        Flask Response object
    """
    l_cl = get_alert_resolution_list()
    schema = AlertResolutionSchema()

    return response_success("", data=schema.dump(l_cl, many=True))


@manage_alerts_status_blueprint.route('/manage/alert-resolutions/<int:resolution_id>', methods=['GET'])
@ac_api_requires()
def get_case_alert_resolution(resolution_id: int) -> Response:
    """
    Get the alert resolution

    Args:
        resolution_id (int): resolution id
        caseid (int): case id
    """
    cl = get_alert_resolution_by_id(resolution_id)
    schema = AlertResolutionSchema()

    return response_success("", data=schema.dump(cl))


@manage_alerts_status_blueprint.route('/manage/alert-resolutions/search', methods=['POST'])
@ac_api_requires()
def search_alert_resolution():
    if not request.is_json:
        return response_error("Invalid request")

    alert_resolution = request.json.get('alert_resolution_name')
    if alert_resolution is None:
        return response_error("Invalid alert resolution. Got None")

    exact_match = request.json.get('exact_match', False)

    # Search for alerts resolution with a name that contains the specified search term
    alert_res = search_alert_resolution_by_name(alert_resolution, exact_match=exact_match)
    if not alert_res:
        return response_error("No alert resolution found")

    # Serialize the alert_res and return them in a JSON response
    schema = AlertResolutionSchema(many=True)
    return response_success("", data=schema.dump(alert_res))
