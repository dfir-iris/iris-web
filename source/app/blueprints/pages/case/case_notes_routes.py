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

from app.datamgmt.case.case_db import case_get_desc_crc
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_notes_db import get_note
from app.models.authorization import CaseAccessLevel
from app.blueprints.access_controls import ac_case_requires
from app.blueprints.responses import response_error

case_notes_blueprint = Blueprint('case_notes',
                                 __name__,
                                 template_folder='templates')


@case_notes_blueprint.route('/case/notes', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_notes(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_notes.case_notes', cid=caseid, redirect=True))

    form = FlaskForm()
    case = get_case(caseid)

    if case:
        crc32, desc = case_get_desc_crc(caseid)
    else:
        crc32 = None
        desc = None

    return render_template('case_notes_v2.html', case=case, form=form, th_desc=desc, crc=crc32)


@case_notes_blueprint.route('/case/notes/<int:cur_id>/comments/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_note_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_note.case_note', cid=caseid, redirect=True))

    note = get_note(cur_id)
    if not note:
        return response_error('Invalid note ID')

    return render_template("modal_conversation.html", element_id=cur_id, element_type='notes',
                           title=note.note_title)
