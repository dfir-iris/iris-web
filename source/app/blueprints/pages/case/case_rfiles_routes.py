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

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import url_for
from flask_wtf import FlaskForm

from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_rfiles_db import get_case_evidence_comments_count
from app.datamgmt.case.case_rfiles_db import get_rfile
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.models.authorization import CaseAccessLevel
from app.blueprints.access_controls import ac_case_requires
from app.blueprints.responses import response_error

case_rfiles_blueprint = Blueprint(
    'case_rfiles',
    __name__,
    template_folder='templates'
)


@case_rfiles_blueprint.route('/case/evidences', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_rfile(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_rfiles.case_rfile', cid=caseid, redirect=True))

    form = FlaskForm()
    case = get_case(caseid)

    return render_template("case_rfile.html", case=case, form=form)


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
@ac_case_requires(CaseAccessLevel.full_access)
def case_add_rfile_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_rfiles.case_rfile', cid=caseid, redirect=True))

    return render_template("modal_add_case_rfile.html", rfile=None, attributes=get_default_custom_attributes('evidence'))


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
