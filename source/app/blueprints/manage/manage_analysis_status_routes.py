#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
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

from flask import Blueprint, request
from werkzeug import Response

from app.datamgmt.case.case_assets_db import get_compromise_status_dict
from app.datamgmt.case.case_assets_db import get_case_outcome_status_dict
from app.datamgmt.manage.manage_case_objs import search_analysis_status_by_name
from app.models.models import AnalysisStatus
from app.schema.marshables import AnalysisStatusSchema
from app.util import ac_api_requires
from app.util import response_error
from app.util import response_success

manage_anastatus_blueprint = Blueprint('manage_anastatus', __name__, template_folder='templates')


# CONTENT ------------------------------------------------
@manage_anastatus_blueprint.route('/manage/analysis-status/list', methods=['GET'])
@ac_api_requires()
def list_anastatus():
    lstatus = AnalysisStatus.query.with_entities(
        AnalysisStatus.id,
        AnalysisStatus.name
    ).all()

    data = [row._asdict() for row in lstatus]

    return response_success("", data=data)


@manage_anastatus_blueprint.route('/manage/compromise-status/list', methods=['GET'])
@ac_api_requires()
def list_compr_status():
    compro_status = get_compromise_status_dict()

    return response_success("", data=compro_status)


@manage_anastatus_blueprint.route('/manage/outcome-status/list', methods=['GET'])
@ac_api_requires()
def list_outcome_status() -> Response:
    """ Returns a list of outcome status

    Args:
        caseid (int): Case ID

    Returns:
        Response: Flask response object

    """
    outcome_status = get_case_outcome_status_dict()

    return response_success("", data=outcome_status)


@manage_anastatus_blueprint.route('/manage/analysis-status/<int:cur_id>', methods=['GET'])
@ac_api_requires()
def view_anastatus(cur_id):
    lstatus = AnalysisStatus.query.with_entities(
        AnalysisStatus.id,
        AnalysisStatus.name
    ).filter(
        AnalysisStatus.id == cur_id
    ).first()

    if not lstatus:
        return response_error(f"Analysis status ID {cur_id} not found")

    return response_success("", data=lstatus._asdict())


@manage_anastatus_blueprint.route('/manage/analysis-status/search', methods=['POST'])
@ac_api_requires()
def search_analysis_status():
    if not request.is_json:
        return response_error("Invalid request")

    analysis_status = request.json.get('analysis_status')
    if analysis_status is None:
        return response_error("Invalid analysis status. Got None")

    exact_match = request.json.get('exact_match', False)

    # Search for analysis status with a name that contains the specified search term
    analysis_status = search_analysis_status_by_name(analysis_status, exact_match=exact_match)
    if not analysis_status:
        return response_error("No analysis status found")

    # Serialize the analysis status and return them in a JSON response
    schema = AnalysisStatusSchema(many=True)
    return response_success("", data=schema.dump(analysis_status))

# TODO : Add management of analysis status
