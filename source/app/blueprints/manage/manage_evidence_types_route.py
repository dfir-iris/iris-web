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
import marshmallow
from typing import Union

from flask import Blueprint
from flask import Response
from flask import url_for
from flask import render_template
from flask import request
from werkzeug.utils import redirect

from app import db
from app.datamgmt.manage.manage_evidence_types_db import get_evidence_types_list
from app.datamgmt.manage.manage_evidence_types_db import get_evidence_type_by_id
from app.datamgmt.manage.manage_evidence_types_db import verify_evidence_type_in_use
from app.forms import EvidenceTypeForm
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.schema.marshables import EvidenceTypeSchema
from app.util import ac_api_requires
from app.util import response_error
from app.util import ac_requires
from app.util import response_success

manage_evidence_types_blueprint = Blueprint('manage_evidence_types',
                                            __name__,
                                            template_folder='templates')


# CONTENT ------------------------------------------------
@manage_evidence_types_blueprint.route('/manage/evidence-types/list', methods=['GET'])
@ac_api_requires()
def list_evidence_types() -> Response:
    """Get the list of evidence types

    Returns:
        Flask Response object

    """
    l_cl = get_evidence_types_list()

    return response_success("", data=l_cl)


@manage_evidence_types_blueprint.route('/manage/evidence-types/<int:evidence_type_id>', methods=['GET'])
@ac_api_requires()
def get_evidence_type(evidence_type_id: int) -> Response:
    """Get an evidence type

    Args:
        evidence_type (int): evidence type ID
        caseid (int): case id

    Returns:
        Flask Response object
    """

    evidence_type_schema = EvidenceTypeSchema()
    evidence_type = get_evidence_type_by_id(evidence_type_id)
    if evidence_type is None:
        return response_error(f"Invalid evidence type ID {evidence_type_id}")

    return response_success("", data=evidence_type_schema.dump(evidence_type))


@manage_evidence_types_blueprint.route('/manage/evidence-types/update/<int:evidence_type_id>/modal',
                                       methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def update_evidence_type_modal(evidence_type_id: int, caseid: int, url_redir: bool) -> Union[str, Response]:
    """Update an evidence type

    Args:
        evidence_type_id (int): evidence type id
        caseid (int): case id
        url_redir (bool): redirect to url

    Returns:
        Flask Response object or str
    """
    if url_redir:
        return redirect(url_for('manage_evidence_types_blueprint.update_evidence_type_modal',
                                evidence_type_id=evidence_type_id, caseid=caseid))

    evidence_type_form = EvidenceTypeForm()
    evidence_type = get_evidence_type_by_id(evidence_type_id)
    if not evidence_type:
        return response_error(f"Invalid evidence type ID {evidence_type_id}")

    evidence_type_form.name.render_kw = {'value': evidence_type.name}
    evidence_type_form.description.render_kw = {'value': evidence_type.description}

    return render_template("modal_evidence_types.html", form=evidence_type_form,
                           evidence_type=evidence_type)


@manage_evidence_types_blueprint.route('/manage/evidence-types/update/<int:evidence_type_id>',
                                       methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def update_case_classification(evidence_type_id: int) -> Response:
    """Update an evidence type

    Args:
        evidence_type_id (int): evidence type id

    Returns:
        Flask Response object
    """
    if not request.is_json:
        return response_error("Invalid request")

    evidence_type = get_evidence_type_by_id(evidence_type_id)
    if not evidence_type:
        return response_error(f"Invalid evidence type ID {evidence_type_id}")

    ccl = EvidenceTypeSchema()

    try:

        ccls = ccl.load(request.get_json(), instance=evidence_type)

        if ccls:
            track_activity(f"updated evidence type {ccls.id}")
            return response_success("Evidence type updated", ccl.dump(ccls))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    return response_error("Unexpected error server-side. Nothing updated", data=evidence_type)


@manage_evidence_types_blueprint.route('/manage/evidence-types/add/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def add_evidence_type_modal(caseid: int, url_redir: bool) -> Union[str, Response]:
    """Add an evidence type

    Args:
        caseid (int): case id
        url_redir (bool): redirect to url

    Returns:
        Flask Response object or str
    """
    if url_redir:
        return redirect(url_for('manage_evidence_types_blueprint.add_evidence_type_modal',
                                caseid=caseid))

    evidence_form = EvidenceTypeForm()

    return render_template("modal_evidence_types.html", form=evidence_form, evidence_type=None)


@manage_evidence_types_blueprint.route('/manage/evidence-types/add', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def add_evidence_type() -> Response:
    """Add an evidence type

    Returns:
        Flask Response object
    """
    if not request.is_json:
        return response_error("Invalid request")

    ccl = EvidenceTypeSchema()

    try:

        ccls = ccl.load(request.get_json())

        if ccls:
            db.session.add(ccls)
            db.session.commit()

            track_activity(f"added evidence type {ccls.name}")
            return response_success("Evidence type added", ccl.dump(ccls))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    return response_error("Unexpected error server-side. Nothing added", data=None)


@manage_evidence_types_blueprint.route('/manage/evidence-types/delete/<int:evidence_type_id>',
                                       methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def delete_evidence_type(evidence_type_id: int) -> Response:
    """Delete an evidence type

    Args:
        evidence_type_id (int): evidence type id

    Returns:
        Flask Response object
    """
    if verify_evidence_type_in_use(evidence_type_id):
        return response_error("Evidence type is in use. Please delete evidences using this type beforehand.")

    evidence_type = get_evidence_type_by_id(evidence_type_id)
    if not evidence_type:
        return response_error(f"Invalid evidence type ID {evidence_type_id}")

    db.session.delete(evidence_type)
    db.session.commit()

    track_activity(f"deleted evidence type {evidence_type.name}")
    return response_success("Evidence type deleted")


@manage_evidence_types_blueprint.route('/manage/evidence-types/search', methods=['POST'])
@ac_api_requires()
def search_evidence_type():
    if not request.is_json:
        return response_error("Invalid request")

    evidence_type_name = request.json.get('evidence_type_name')
    if evidence_type_name is None:
        return response_error("Invalid evidence type name. Got None")

    exact_match = request.json.get('exact_match', False)

    evidence_type = search_evidence_type(evidence_type_name, exact_match=exact_match)
    if not evidence_type:
        return response_error("No evidence type found")

    schema = EvidenceTypeSchema(many=True)
    return response_success("", data=schema.dump(evidence_type))
