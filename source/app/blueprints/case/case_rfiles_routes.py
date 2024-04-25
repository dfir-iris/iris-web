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

import marshmallow
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from flask_wtf import FlaskForm

from app import db
from app.blueprints.case.case_comments import case_comment_update
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_rfiles_db import add_comment_to_evidence
from app.datamgmt.case.case_rfiles_db import add_rfile
from app.datamgmt.case.case_rfiles_db import delete_evidence_comment
from app.datamgmt.case.case_rfiles_db import delete_rfile
from app.datamgmt.case.case_rfiles_db import get_case_evidence_comment
from app.datamgmt.case.case_rfiles_db import get_case_evidence_comments
from app.datamgmt.case.case_rfiles_db import get_case_evidence_comments_count
from app.datamgmt.case.case_rfiles_db import get_rfile
from app.datamgmt.case.case_rfiles_db import get_rfiles
from app.datamgmt.case.case_rfiles_db import update_rfile
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import get_evidences_state
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import CaseEvidenceSchema
from app.schema.marshables import CommentSchema
from app.util import ac_api_case_requires
from app.util import ac_case_requires
from app.util import response_error
from app.util import response_success

case_rfiles_blueprint = Blueprint(
    'case_rfiles',
    __name__,
    template_folder='templates'
)


# CONTENT ------------------------------------------------
@case_rfiles_blueprint.route('/case/evidences', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_rfile(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_rfiles.case_rfile', cid=caseid, redirect=True))

    form = FlaskForm()
    case = get_case(caseid)

    return render_template("case_rfile.html", case=case, form=form)


@case_rfiles_blueprint.route('/case/evidences/list', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_list_rfiles(caseid):
    crf = get_rfiles(caseid)

    ret = {
        "evidences": CaseEvidenceSchema().dump(crf, many=True),
        "state": get_evidences_state(caseid=caseid)
    }

    return response_success("", data=ret)


@case_rfiles_blueprint.route('/case/evidences/state', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_rfiles_state(caseid):
    os = get_evidences_state(caseid=caseid)
    if os:
        return response_success(data=os)
    else:
        return response_error('No evidences state for this case.')


@case_rfiles_blueprint.route('/case/evidences/add', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_add_rfile(caseid):

    try:
        # validate before saving
        evidence_schema = CaseEvidenceSchema()

        request_data = call_modules_hook('on_preload_evidence_create', data=request.get_json(), caseid=caseid)

        evidence = evidence_schema.load(request_data)

        crf = add_rfile(evidence=evidence,
                        user_id=current_user.id,
                        caseid=caseid
                         )

        crf = call_modules_hook('on_postload_evidence_create', data=crf, caseid=caseid)

        if crf:
            track_activity(f"added evidence \"{crf.filename}\"", caseid=caseid)
            return response_success("Evidence added", data=evidence_schema.dump(crf))

        return response_error("Unable to create task for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@case_rfiles_blueprint.route('/case/evidences/<int:cur_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_get_evidence(cur_id, caseid):
    crf = get_rfile(cur_id, caseid)
    if not crf:
        return response_error("Invalid evidence ID for this case")

    evidence_schema = CaseEvidenceSchema()
    return response_success(data=evidence_schema.dump(crf))


@case_rfiles_blueprint.route('/case/evidences/<int:cur_id>/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_edit_rfile_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_rfiles.case_rfile', cid=caseid, redirect=True))

    crf = get_rfile(cur_id, caseid)
    if not crf:
        return response_error("Invalid evidence ID for this case")

    comments_map = get_case_evidence_comments_count([cur_id])

    return render_template("modal_add_case_rfile.html", rfile=crf, attributes=crf.custom_attributes,
                           comments_map=comments_map)


@case_rfiles_blueprint.route('/case/evidences/add/modal', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_add_rfile_modal(caseid):

    return render_template("modal_add_case_rfile.html", rfile=None, attributes=get_default_custom_attributes('evidence'))


@case_rfiles_blueprint.route('/case/evidences/update/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_edit_rfile(cur_id, caseid):

    try:
        # validate before saving
        evidence_schema = CaseEvidenceSchema()

        request_data = call_modules_hook('on_preload_evidence_update', data=request.get_json(), caseid=caseid)

        crf = get_rfile(cur_id, caseid)
        if not crf:
            return response_error("Invalid evidence ID for this case")

        request_data['id'] = cur_id
        evidence = evidence_schema.load(request_data, instance=crf)

        evd = update_rfile(evidence=evidence,
                           user_id=current_user.id,
                           caseid=caseid
                           )

        evd = call_modules_hook('on_postload_evidence_update', data=evd, caseid=caseid)

        if evd:
            track_activity(f"updated evidence \"{evd.filename}\"", caseid=caseid)
            return response_success("Evidence {} updated".format(evd.filename), data=evidence_schema.dump(evd))

        return response_error("Unable to update task for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@case_rfiles_blueprint.route('/case/evidences/delete/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_delete_rfile(cur_id, caseid):

    call_modules_hook('on_preload_evidence_delete', data=cur_id, caseid=caseid)
    crf = get_rfile(cur_id, caseid)
    if not crf:
        return response_error("Invalid evidence ID for this case")

    delete_rfile(cur_id, caseid=caseid)

    call_modules_hook('on_postload_evidence_delete', data=cur_id, caseid=caseid)

    track_activity(f"deleted evidence \"{crf.filename}\" from registry", caseid)

    return response_success("Evidence deleted")


@case_rfiles_blueprint.route('/case/evidences/<int:cur_id>/comments/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_evidence_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_task.case_task', cid=caseid, redirect=True))

    evidence = get_rfile(cur_id, caseid=caseid)
    if not evidence:
        return response_error('Invalid evidence ID')

    return render_template("modal_conversation.html", element_id=cur_id, element_type='evidences',
                           title=evidence.filename)


@case_rfiles_blueprint.route('/case/evidences/<int:cur_id>/comments/list', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_evidence_list(cur_id, caseid):

    evidence_comments = get_case_evidence_comments(cur_id)
    if evidence_comments is None:
        return response_error('Invalid evidence ID')

    return response_success(data=CommentSchema(many=True).dump(evidence_comments))


@case_rfiles_blueprint.route('/case/evidences/<int:cur_id>/comments/add', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_evidence_add(cur_id, caseid):

    try:
        evidence = get_rfile(cur_id, caseid=caseid)
        if not evidence:
            return response_error('Invalid evidence ID')

        comment_schema = CommentSchema()

        comment = comment_schema.load(request.get_json())
        comment.comment_case_id = caseid
        comment.comment_user_id = current_user.id
        comment.comment_date = datetime.now()
        comment.comment_update_date = datetime.now()
        db.session.add(comment)
        db.session.commit()

        add_comment_to_evidence(evidence.id, comment.comment_id)

        db.session.commit()

        hook_data = {
            "comment": comment_schema.dump(comment),
            "evidence": CaseEvidenceSchema().dump(evidence)
        }
        call_modules_hook('on_postload_evidence_commented', data=hook_data, caseid=caseid)

        track_activity(f"evidence \"{evidence.filename}\" commented", caseid=caseid)
        return response_success("Event commented", data=comment_schema.dump(comment))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages())


@case_rfiles_blueprint.route('/case/evidences/<int:cur_id>/comments/<int:com_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_evidence_get(cur_id, com_id, caseid):

    comment = get_case_evidence_comment(cur_id, com_id)
    if not comment:
        return response_error("Invalid comment ID")

    return response_success(data=comment._asdict())


@case_rfiles_blueprint.route('/case/evidences/<int:cur_id>/comments/<int:com_id>/edit', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_evidence_edit(cur_id, com_id, caseid):

    return case_comment_update(com_id, 'tasks', caseid)


@case_rfiles_blueprint.route('/case/evidences/<int:cur_id>/comments/<int:com_id>/delete', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_evidence_delete(cur_id, com_id, caseid):

    success, msg = delete_evidence_comment(cur_id, com_id)
    if not success:
        return response_error(msg)

    call_modules_hook('on_postload_evidence_comment_delete', data=com_id, caseid=caseid)

    track_activity(f"comment {com_id} on evidence {cur_id} deleted", caseid=caseid)
    return response_success(msg)
