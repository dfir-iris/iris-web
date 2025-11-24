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
import marshmallow
from flask import Blueprint
from flask import render_template
from flask import request
from flask import url_for
from werkzeug.utils import redirect

from app import db
from app.datamgmt.case.case_artifacts_db import get_artifact_types_list
from app.datamgmt.manage.manage_case_objs import search_ioc_type_by_name
from app.forms import AddArtifactTypeForm
from app.iris_engine.utils.tracker import track_activity
from app.models.models import Artifact
from app.models.models import IocType
from app.models.authorization import Permissions
from app.schema.marshables import ArtifactTypeSchema
from app.util import ac_api_requires
from app.util import ac_requires
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success

manage_artifact_type_blueprint = Blueprint('manage_artifact_types', __name__, template_folder='templates')




# CONTENT ------------------------------------------------
@manage_artifact_type_blueprint.route('/manage/artifact-types/list', methods=['GET'])
@ac_api_requires()
def list_artifact_types():
    lstatus = get_artifact_types_list()

    return response_success("", data=lstatus)


@manage_artifact_type_blueprint.route('/manage/artifact-types/<int:cur_id>', methods=['GET'])
@ac_api_requires()
def get_artifact_type(cur_id):

    artifact_type = IocType.query.filter(IocType.type_id == cur_id).first()
    if not artifact_type:
        return response_error("Invalid artifact type ID {type_id}".format(type_id=cur_id))

    return response_success("", data=artifact_type)


@manage_artifact_type_blueprint.route('/manage/artifact-types/update/<int:cur_id>/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def view_artifact_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_artifact_types.view_artifact_modal', cid=caseid))

    form = AddArtifactTypeForm()
    artifactt = IocType.query.filter(IocType.type_id == cur_id).first()
    if not artifactt:
        return response_error("Invalid asset type ID")

    form.type_name.render_kw = {'value': artifactt.type_name}
    form.type_description.render_kw = {'value': artifactt.type_description}
    form.type_taxonomy.data = artifactt.type_taxonomy
    form.type_validation_regex.data = artifactt.type_validation_regex
    form.type_validation_expect.data = artifactt.type_validation_expect

    return render_template("modal_add_artifact_type.html", form=form, artifact_type=artifactt)


@manage_artifact_type_blueprint.route('/manage/artifact-types/add/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def add_artifact_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_artifact_types.view_artifact_modal', cid=caseid))

    form = AddArtifactTypeForm()

    return render_template("modal_add_artifact_type.html", form=form, artifact_type=None)


@manage_artifact_type_blueprint.route('/manage/artifact-types/add', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def add_artifact_type_api():
    if not request.is_json:
        return response_error("Invalid request")

    artifactt_schema = ArtifactTypeSchema()

    try:

        artifactt_sc = artifactt_schema.load(request.get_json())
        db.session.add(artifactt_sc)
        db.session.commit()

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    track_activity("Added artifact type {artifact_type_name}".format(artifact_type_name=artifactt_sc.type_name), ctx_less=True)
    # Return the assets
    return response_success("Added successfully", data=artifactt_sc)


@manage_artifact_type_blueprint.route('/manage/artifact-types/delete/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def remove_artifact_type(cur_id):

    type_id = IocType.query.filter(
        IocType.type_id == cur_id
    ).first()

    is_referenced = Artifact.query.filter(Artifact.artifact_type_id == cur_id).first()
    if is_referenced:
        return response_error("Cannot delete a referenced artifact type. Please delete any artifact of this type first.")

    if type_id:
        db.session.delete(type_id)
        track_activity("Deleted artifact type ID {type_id}".format(type_id=cur_id), ctx_less=True)
        return response_success("Deleted artifact type ID {type_id}".format(type_id=cur_id))

    track_activity(f'Attempted to delete artifact type ID {cur_id}, but was not found', ctx_less=True)

    return response_error("Attempted to delete artifact type ID {type_id}, but was not found".format(type_id=cur_id))


@manage_artifact_type_blueprint.route('/manage/artifact-types/update/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def update_artifact(cur_id):
    if not request.is_json:
        return response_error("Invalid request")

    artifact_type = IocType.query.filter(IocType.type_id == cur_id).first()
    if not artifact_type:
        return response_error("Invalid artifact type ID {type_id}".format(type_id=cur_id))

    artifactt_schema = ArtifactTypeSchema()

    try:

        artifactt_sc = artifactt_schema.load(request.get_json(), instance=artifact_type)

        if artifactt_sc:
            track_activity("updated artifact type type {}".format(artifactt_sc.type_name))
            return response_success("Artifact type updated", artifactt_sc)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    return response_error("Unexpected error server-side. Nothing updated", data=artifact_type)


@manage_artifact_type_blueprint.route('/manage/artifact-types/search', methods=['POST'])
@ac_api_requires()
def search_artifact_type():
    """Searches for Artifact types in the database.

    This function searches for Artifact types in the database with a name that contains the specified search term.
    It returns a JSON response containing the matching Artifact types.

    Returns:
        A JSON response containing the matching Artifact types.

    """
    if not request.is_json:
        return response_error("Invalid request")

    artifact_type = request.json.get('artifact_type')
    if artifact_type is None:
        return response_error("Invalid artifact type. Got None")

    exact_match = request.json.get('exact_match', False)
    
    # Search for Artifact types with a name that contains the specified search term
    artifact_type = search_ioc_type_by_name(artifact_type, exact_match=exact_match)
    if not artifact_type:
        return response_error("No artifact types found")
    
    # Serialize the Artifact types and return them in a JSON response
    artifactt_schema = ArtifactTypeSchema(many=True)
    return response_success("", data=artifactt_schema.dump(artifact_type))
