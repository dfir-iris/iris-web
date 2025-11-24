#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS) - DFIR-IRIS Team
#  ir@cyberactionlab.net - contact@dfir-iris.org
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

# IMPORTS ------------------------------------------------
from datetime import datetime

import csv
import logging as log
import marshmallow
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user

from app import db
from app.blueprints.rest.case_comments import case_comment_update
from app.datamgmt.case.case_assets_db import get_assets_types
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_artifacts_db import add_comment_to_artifact
from app.datamgmt.case.case_artifacts_db import add_artifact
from app.datamgmt.case.case_artifacts_db import add_artifact_link
from app.datamgmt.case.case_artifacts_db import delete_artifact_comment
from app.datamgmt.case.case_artifacts_db import get_case_artifact_comment
from app.datamgmt.case.case_artifacts_db import get_case_artifact_comments
from app.datamgmt.case.case_artifacts_db import get_case_artifacts_comments_count
from app.datamgmt.case.case_artifacts_db import get_detailed_artifacts
from app.datamgmt.case.case_artifacts_db import get_artifact
from app.datamgmt.case.case_artifacts_db import get_artifact_links
from app.datamgmt.case.case_artifacts_db import get_artifact_type_id
from app.datamgmt.case.case_artifacts_db import get_artifact_types_list
from app.datamgmt.case.case_artifacts_db import get_tlps
from app.datamgmt.case.case_artifacts_db import get_tlps_dict
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import get_artifact_state
from app.forms import ModalAddCaseAssetForm
from app.forms import ModalAddCaseArtifactForm
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.models.models import Artifact
from app.schema.marshables import CommentSchema
from app.schema.marshables import ArtifactSchema
from app.blueprints.access_controls import ac_api_case_requires
from app.blueprints.access_controls import ac_case_requires
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success
from app.business.artifacts import create
from app.business.artifacts import update
from app.business.artifacts import escalate
from app.business.artifacts import delete
from app.business.errors import BusinessProcessingError

case_artifact_blueprint = Blueprint(
    'case_artifact',
    __name__,
    template_folder='templates'
)


# CONTENT ------------------------------------------------
@case_artifact_blueprint.route('/case/artifact', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_artifact(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_artifact.case_artifact', cid=caseid, redirect=True))

    form = ModalAddCaseAssetForm()
    form.asset_id.choices = get_assets_types()

    # Retrieve the assets linked to the investigation
    case = get_case(caseid)

    return render_template("case_artifact.html", case=case, form=form)


@case_artifact_blueprint.route('/case/artifact/list', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_list_artifact(caseid):
    artifacts = get_detailed_artifacts(caseid)

    ret = {}
    ret['artifact'] = []

    for artifact in artifacts:
        out = artifact._asdict()

        # Get links of the Artifacts seen in other cases
        ial = get_artifact_links(artifact.artifact_id, caseid)

        out['link'] = [row._asdict() for row in ial]
        # Legacy, must be changed next version
        out['misp_link'] = None

        ret['artifact'].append(out)

    ret['state'] = get_artifact_state(caseid=caseid)

    return response_success("", data=ret)


@case_artifact_blueprint.route('/case/artifact/state', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_artifact_state(caseid):
    os = get_artifact_state(caseid=caseid)
    if os:
        return response_success(data=os)
    else:
        return response_error('No Artifact state for this case.')


@case_artifact_blueprint.route('/case/artifact/add', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_add_artifact(caseid):
    artifact_schema = ArtifactSchema()

    try:
        artifact, msg = create(request.get_json(), caseid)
        return response_success(msg, data=artifact_schema.dump(artifact))
    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@case_artifact_blueprint.route('/case/artifact/upload', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_upload_artifact(caseid):
    try:
        # validate before saving
        add_artifact_schema = ArtifactSchema()
        jsdata = request.get_json()

        # get Artifact list from request
        headers = "artifact_value,artifact_type,artifact_description,artifact_tags,artifact_tlp"
        csv_lines = jsdata["CSVData"].splitlines()  # unavoidable since the file is passed as a string
        if csv_lines[0].lower() != headers:
            csv_lines.insert(0, headers)

        # convert list of strings into CSV
        csv_data = csv.DictReader(csv_lines, quotechar='"', delimiter=',')

        # build a Dict of possible TLP
        tlp_dict = get_tlps_dict()
        ret = []
        errors = []

        index = 0
        for row in csv_data:

            for e in headers.split(','):
                if row.get(e) is None:
                    errors.append(f"{e} is missing for row {index}")
                    index += 1
                    continue

            # Artifact value must not be empty
            if not row.get("artifact_value"):
                errors.append(f"Empty Artifact value for row {index}")
                track_activity(f"Attempted to upload an empty Artifact value")
                index += 1
                continue

            row["artifact_tags"] = row["artifact_tags"].replace("|", ",")  # Reformat Tags

            # Convert TLP into TLP id
            if row["artifact_tlp"] in tlp_dict:
                row["artifact_tlp_id"] = tlp_dict[row["artifact_tlp"]]
            else:
                row["artifact_tlp_id"] = ""
            row.pop("artifact_tlp", None)

            type_id = get_artifact_type_id(row['artifact_type'].lower())
            if not type_id:
                errors.append(f"{row['artifact_value']} (invalid artifact type: {row['artifact_type']}) for row {index}")
                log.error(f'Unrecognised Artifact type {row["artifact_type"]}')
                index += 1
                continue

            row['artifact_type_id'] = type_id.type_id
            row.pop('artifact_type', None)

            request_data = call_modules_hook('on_preload_artifact_create', data=row, caseid=caseid)

            artifact = add_artifact_schema.load(request_data)
            artifact.custom_attributes = get_default_custom_attributes('artifact')
            artifact, existed = add_artifact(artifact=artifact,
                                   user_id=current_user.id,
                                   caseid=caseid
                                   )
            link_existed = add_artifact_link(artifact.artifact_id, caseid)

            if link_existed:
                errors.append(f"{artifact.artifact_value} (already exists and linked to this case)")
                log.error(f"Artifact {artifact.artifact_value} already exists and linked to this case")
                index += 1
                continue

            if artifact:
                artifact = call_modules_hook('on_postload_artifact_create', data=artifact, caseid=caseid)
                ret.append(request_data)
                track_activity(f"added artifact \"{artifact.artifact_value}\"", caseid=caseid)

            else:
                errors.append(f"{artifact.artifact_value} (internal reasons)")
                log.error(f"Unable to create Artifact {artifact.artifact_value} for internal reasons")

            index += 1

        if len(errors) == 0:
            msg = "Successfully imported data."
        else:
            msg = "Data is imported but we got errors with the following rows:\n- " + "\n- ".join(errors)

        return response_success(msg=msg, data=ret)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@case_artifact_blueprint.route('/case/artifact/add/modal', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_add_artifact_modal(caseid):

    form = ModalAddCaseArtifactForm()
    form.artifact_type_id.choices = [(row['type_id'], row['type_name']) for row in get_artifact_types_list()]
    form.artifact_tlp_id.choices = get_tlps()

    attributes = get_default_custom_attributes('artifact')

    return render_template("modal_add_case_artifact.html", form=form, artifact=Artifact(), attributes=attributes)


@case_artifact_blueprint.route('/case/artifact/delete/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_delete_artifact(cur_id, caseid):
    try:

        msg = delete(cur_id, caseid)
        return response_success(msg=msg)

    except BusinessProcessingError as e:
        return response_error(e.get_message())


@case_artifact_blueprint.route('/case/artifact/<int:cur_id>/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_view_artifact_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_assets.case_assets', cid=caseid, redirect=True))

    form = ModalAddCaseArtifactForm()
    artifact = get_artifact(cur_id, caseid)
    if not artifact:
        return response_error("Invalid Artifact ID for this case")

    form.artifact_type_id.choices = [(row['type_id'], row['type_name']) for row in get_artifact_types_list()]
    form.artifact_tlp_id.choices = get_tlps()

    # Render the Artifact
    form.artifact_tags.render_kw = {'value': artifact.artifact_tags}
    form.artifact_description.data = artifact.artifact_description
    form.artifact_value.data = artifact.artifact_value
    comments_map = get_case_artifacts_comments_count([cur_id])

    return render_template("modal_add_case_artifact.html", form=form, artifact=artifact, attributes=artifact.custom_attributes,
                           comments_map=comments_map)


@case_artifact_blueprint.route('/case/artifact/<int:cur_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_view_artifact(cur_id, caseid):
    artifact_schema = ArtifactSchema()
    artifact = get_artifact(cur_id, caseid)
    if not artifact:
        return response_error("Invalid Artifact ID for this case")

    return response_success(data=artifact_schema.dump(artifact))


@case_artifact_blueprint.route('/case/artifact/update/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_update_artifact(cur_id, caseid):
    artifact_schema = ArtifactSchema()

    try:
        artifact, msg = update(cur_id, request.get_json(), caseid)
        return response_success(msg, data=artifact_schema.dump(artifact))
    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())

@case_artifact_blueprint.route('/case/artifact/escalate/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_escalate_artifact(cur_id, caseid):
    try:
        msg = escalate(cur_id, caseid)
        return response_success(msg=msg)

    except BusinessProcessingError as e:
        return response_error(e.get_message())

@case_artifact_blueprint.route('/case/artifact/<int:cur_id>/comments/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_artifact_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_artifact.case_artifact', cid=caseid, redirect=True))

    artifact = get_artifact(cur_id, caseid=caseid)
    if not artifact:
        return response_error('Invalid artifact ID')

    return render_template("modal_conversation.html", element_id=cur_id, element_type='artifact',
                           title=artifact.artifact_value)


@case_artifact_blueprint.route('/case/artifact/<int:cur_id>/comments/list', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_artifact_list(cur_id, caseid):

    artifact_comments = get_case_artifact_comments(cur_id)
    if artifact_comments is None:
        return response_error('Invalid artifact ID')

    return response_success(data=CommentSchema(many=True).dump(artifact_comments))


@case_artifact_blueprint.route('/case/artifact/<int:cur_id>/comments/add', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_artifact_add(cur_id, caseid):

    try:
        artifact = get_artifact(cur_id, caseid=caseid)
        if not artifact:
            return response_error('Invalid artifact ID')

        comment_schema = CommentSchema()

        comment = comment_schema.load(request.get_json())
        comment.comment_case_id = caseid
        comment.comment_user_id = current_user.id
        comment.comment_date = datetime.now()
        comment.comment_update_date = datetime.now()
        db.session.add(comment)
        db.session.commit()

        add_comment_to_artifact(artifact.artifact_id, comment.comment_id)

        db.session.commit()

        hook_data = {
            "comment": comment_schema.dump(comment),
            "artifact": ArtifactSchema().dump(artifact)
        }
        call_modules_hook('on_postload_artifact_commented', data=hook_data, caseid=caseid)

        track_activity(f"artifact \"{artifact.artifact_value}\" commented", caseid=caseid)
        return response_success("Event commented", data=comment_schema.dump(comment))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages())


@case_artifact_blueprint.route('/case/artifact/<int:cur_id>/comments/<int:com_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_artifact_get(cur_id, com_id, caseid):

    comment = get_case_artifact_comment(cur_id, com_id)
    if not comment:
        return response_error("Invalid comment ID")

    return response_success(data=comment._asdict())


@case_artifact_blueprint.route('/case/artifact/<int:cur_id>/comments/<int:com_id>/edit', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_artifact_edit(cur_id, com_id, caseid):

    return case_comment_update(com_id, 'artifact', caseid)


@case_artifact_blueprint.route('/case/artifact/<int:cur_id>/comments/<int:com_id>/delete', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_artifact_delete(cur_id, com_id, caseid):

    success, msg = delete_artifact_comment(cur_id, com_id)
    if not success:
        return response_error(msg)

    call_modules_hook('on_postload_artifact_comment_delete', data=com_id, caseid=caseid)

    track_activity(f"comment {com_id} on artifact {cur_id} deleted", caseid=caseid)
    return response_success(msg)
