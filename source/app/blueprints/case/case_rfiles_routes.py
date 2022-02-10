#!/usr/bin/env python3
#
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

# IMPORTS ------------------------------------------------
import marshmallow
from flask import Blueprint, request
from flask import render_template, url_for, redirect
from flask_login import current_user
from flask_wtf import FlaskForm

from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_rfiles_db import get_rfiles, add_rfile, get_rfile, update_rfile, delete_rfile
from app.datamgmt.states import get_evidences_state
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import CaseEvidenceSchema
from app.util import response_success, response_error, login_required, api_login_required

case_rfiles_blueprint = Blueprint(
    'case_rfiles',
    __name__,
    template_folder='templates'
)


# CONTENT ------------------------------------------------
@case_rfiles_blueprint.route('/case/evidences', methods=['GET'])
@login_required
def case_rfile(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_rfiles.case_rfile', cid=caseid))

    form = FlaskForm()
    case = get_case(caseid)

    return render_template("case_rfile.html", case=case, form=form)


@case_rfiles_blueprint.route('/case/evidences/list', methods=['GET'])
@api_login_required
def case_list_rfiles(caseid):
    crf = get_rfiles(caseid)

    ret = {
        "evidences": [row._asdict() for row in crf],
        "state": get_evidences_state(caseid=caseid)
    }

    return response_success("", data=ret)


@case_rfiles_blueprint.route('/case/evidences/state', methods=['GET'])
@api_login_required
def case_rfiles_state(caseid):
    os = get_evidences_state(caseid=caseid)
    if os:
        return response_success(data=os)
    else:
        return response_error('No evidences state for this case.')


@case_rfiles_blueprint.route('/case/evidences/add', methods=['POST'])
@api_login_required
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
            track_activity("added evidence {}".format(crf.filename), caseid=caseid)
            return response_success(data=evidence_schema.dump(crf))

        return response_error("Unable to create task for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@case_rfiles_blueprint.route('/case/evidences/<int:cur_id>', methods=['GET'])
@api_login_required
def case_get_evidence(cur_id, caseid):
    crf = get_rfile(cur_id, caseid)
    if not crf:
        return response_error("Invalid evidence ID for this case")

    evidence_schema = CaseEvidenceSchema()
    return response_success(data=evidence_schema.dump(crf))


@case_rfiles_blueprint.route('/case/evidences/<int:cur_id>/modal', methods=['GET'])
@login_required
def case_edit_rfile_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_rfiles.case_rfile', cid=caseid))

    crf = get_rfile(cur_id, caseid)
    if not crf:
        return response_error("Invalid evidence ID for this case")

    return render_template("modal_edit_case_rfile.html", rfile=crf)


@case_rfiles_blueprint.route('/case/evidences/update/<int:cur_id>', methods=['POST'])
@api_login_required
def case_edit_rfile(cur_id, caseid):

    try:
        # validate before saving
        evidence_schema = CaseEvidenceSchema()

        request_data = call_modules_hook('on_preload_evidence_update', data=request.get_json(), caseid=caseid)

        crf = get_rfile(cur_id, caseid)
        if not crf:
            return response_error("Invalid evidence ID for this case")

        evidence = evidence_schema.load(request_data, instance=crf)

        evd = update_rfile(evidence=evidence,
                             user_id=current_user.id,
                             caseid=caseid
                            )

        evd = call_modules_hook('on_postload_evidence_update', data=evd, caseid=caseid)

        if evd:
            track_activity("updated evidence {}".format(evd.filename), caseid=caseid)
            return response_success(data=evidence_schema.dump(evd))

        return response_error("Unable to update task for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@case_rfiles_blueprint.route('/case/evidences/delete/<int:cur_id>', methods=['GET'])
@api_login_required
def case_delete_rfile(cur_id, caseid):

    call_modules_hook('on_preload_evidence_delete', data=cur_id, caseid=caseid)
    crf = get_rfile(cur_id, caseid)
    if not crf:
        return response_error("Invalid evidence ID for this case")

    delete_rfile(cur_id, caseid=caseid)

    call_modules_hook('on_postload_evidence_delete', data=cur_id, caseid=caseid)

    track_activity("deleted evidence ID {} from register".format(cur_id), caseid)

    return response_success("Evidence deleted")
