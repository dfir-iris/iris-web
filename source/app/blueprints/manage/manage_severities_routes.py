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

from app.datamgmt.manage.manage_common import get_severity_by_id, get_severities_list, search_severity_by_name
from app.schema.marshables import SeveritySchema
from app.util import ac_api_requires, response_error
from app.util import response_success

manage_severities_blueprint = Blueprint('manage_severities',
                                        __name__,
                                        template_folder='templates')


# CONTENT ------------------------------------------------
@manage_severities_blueprint.route('/manage/severities/list', methods=['GET'])
@ac_api_requires(no_cid_required=True)
def list_severities(caseid: int) -> Response:
    """
    Get the list of severities

    Args:
        caseid (int): case id

    Returns:
        Flask Response object
    """
    l_cl = get_severities_list()
    schema = SeveritySchema()

    return response_success("", data=schema.dump(l_cl, many=True))


@manage_severities_blueprint.route('/manage/severities/<int:severity_id>', methods=['GET'])
@ac_api_requires(no_cid_required=True)
def get_case_alert_status(severity_id: int, caseid: int) -> Response:
    """
    Get the alert status

    Args:
        severity_id (int): severity id
        caseid (int): case id
    """
    cl = get_severity_by_id(severity_id)
    schema = SeveritySchema()

    return response_success("", data=schema.dump(cl))


@manage_severities_blueprint.route('/manage/severities/search', methods=['POST'])
@ac_api_requires(no_cid_required=True)
def search_analysis_status(caseid):
    if not request.is_json:
        return response_error("Invalid request")

    severity_name = request.json.get('severity_name')
    if severity_name is None:
        return response_error("Invalid severity. Got None")

    exact_match = request.json.get('exact_match', False)

    # Search for severity with a name that contains the specified search term
    severity = search_severity_by_name(severity_name, exact_match=exact_match)
    if not severity:
        return response_error("No severity found")

    # Serialize the severity and return them in a JSON response
    schema = SeveritySchema(many=True)
    return response_success("", data=schema.dump(severity))
