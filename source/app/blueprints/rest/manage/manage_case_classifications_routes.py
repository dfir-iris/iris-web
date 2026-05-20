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

import marshmallow

from flask import Blueprint
from flask import Response
from flask import request

from app.db import db
from app.datamgmt.manage.manage_case_classifications_db import get_case_classifications_list
from app.datamgmt.manage.manage_case_classifications_db import get_case_classification_by_id
from app.datamgmt.manage.manage_case_classifications_db import search_classification_by_name
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.schema.marshables import CaseClassificationSchema
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success

manage_case_classification_rest_blueprint = Blueprint('manage_case_classifications_rest', __name__)


@manage_case_classification_rest_blueprint.route('/manage/case-classifications/list', methods=['GET'])
@ac_api_requires()
def list_case_classifications() -> Response:
    """Get the list of case classifications

    Args:
        caseid (int): case id

    Returns:
        Flask Response object

    """
    l_cl = get_case_classifications_list()

    return response_success("", data=l_cl)


@manage_case_classification_rest_blueprint.route('/manage/case-classifications/<int:classification_id>', methods=['GET'])
@ac_api_requires()
def get_case_classification(classification_id: int) -> Response:
    """Get a case classification

    Args:
        classification_id (int): case classification id
        caseid (int): case id

    Returns:
        Flask Response object
    """
    schema = CaseClassificationSchema()
    case_classification = get_case_classification_by_id(classification_id)
    if not case_classification:
        return response_error(f"Invalid case classification ID {classification_id}")

    return response_success("", data=schema.dump(case_classification))


@manage_case_classification_rest_blueprint.route('/manage/case-classifications/update/<int:classification_id>',
                                                 methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def update_case_classification(classification_id: int) -> Response:
    """Update a case classification

    Args:
        classification_id (int): case classification id
        caseid (int): case id

    Returns:
        Flask Response object
    """
    if not request.is_json:
        return response_error("Invalid request")

    case_classification = get_case_classification_by_id(classification_id)
    if not case_classification:
        return response_error(f"Invalid case classification ID {classification_id}")

    ccl = CaseClassificationSchema()

    try:

        ccls = ccl.load(request.get_json(), instance=case_classification)

        if ccls:
            track_activity(f"updated case classification {ccls.id}")
            return response_success("Case classification updated", ccl.dump(ccls))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    return response_error("Unexpected error server-side. Nothing updated", data=case_classification)


@manage_case_classification_rest_blueprint.route('/manage/case-classifications/add', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def add_case_classification() -> Response:
    """Add a case classification

    Returns:
        Flask Response object
    """
    if not request.is_json:
        return response_error("Invalid request")

    ccl = CaseClassificationSchema()

    try:

        ccls = ccl.load(request.get_json())

        if ccls:
            db.session.add(ccls)
            db.session.commit()

            track_activity(f"added case classification {ccls.name}")
            return response_success("Case classification added", ccl.dump(ccls))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    return response_error("Unexpected error server-side. Nothing added", data=None)


@manage_case_classification_rest_blueprint.route('/manage/case-classifications/delete/<int:classification_id>',
                                                 methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def delete_case_classification(classification_id: int) -> Response:
    """Delete a case classification

    Args:
        classification_id (int): case classification id
        caseid (int): case id

    Returns:
        Flask Response object
    """
    case_classification = get_case_classification_by_id(classification_id)
    if not case_classification:
        return response_error(f"Invalid case classification ID {classification_id}")

    db.session.delete(case_classification)
    db.session.commit()

    track_activity(f"deleted case classification {case_classification.name}")
    return response_success("Case classification deleted")


@manage_case_classification_rest_blueprint.route('/manage/case-classifications/search', methods=['POST'])
@ac_api_requires()
def search_alert_status():
    if not request.is_json:
        return response_error("Invalid request")

    classification_name = request.json.get('classification_name')
    if classification_name is None:
        return response_error("Invalid classification name. Got None")

    exact_match = request.json.get('exact_match', False)

    # Search for classifications with a name that contains the specified search term
    classification = search_classification_by_name(classification_name, exact_match=exact_match)
    if not classification:
        return response_error("No classification found")

    # Serialize the case classification and return them in a JSON response
    schema = CaseClassificationSchema(many=True)
    return response_success("", data=schema.dump(classification))
