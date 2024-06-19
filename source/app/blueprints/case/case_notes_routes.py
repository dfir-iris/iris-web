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
from flask import request
from flask import url_for
from flask_login import current_user
from flask_socketio import emit
from flask_socketio import join_room
from flask_wtf import FlaskForm

from app import socket_io
from app.datamgmt.case.case_db import case_get_desc_crc
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_notes_db import get_note
from app.models.authorization import CaseAccessLevel
from app.util import ac_socket_requires
from app.util import ac_case_requires
from app.util import response_error


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

    note = get_note(cur_id, caseid=caseid)
    if not note:
        return response_error('Invalid note ID')

    return render_template("modal_conversation.html", element_id=cur_id, element_type='notes',
                           title=note.note_title)


@socket_io.on('change-note')
@ac_socket_requires(CaseAccessLevel.full_access)
def socket_change_note(data):

    data['last_change'] = current_user.user
    emit('change-note', data, to=data['channel'], skip_sid=request.sid, room=data['channel'])


@socket_io.on('save-note')
@ac_socket_requires(CaseAccessLevel.full_access)
def socket_save_note(data):

    data['last_saved'] = current_user.user
    emit('save-note', data, to=data['channel'], skip_sid=request.sid, room=data['channel'])


@socket_io.on('clear_buffer-note')
@ac_socket_requires(CaseAccessLevel.full_access)
def socket_clear_buffer_note(message):

    emit('clear_buffer-note', message, room=message['channel'])


@socket_io.on('join-notes')
@ac_socket_requires(CaseAccessLevel.full_access)
def socket_join_note(data):

    room = data['channel']
    join_room(room=room)

    emit('join-notes', {
        'message': f"{current_user.user} just joined",
        "user": current_user.user
    }, room=room)


@socket_io.on('ping-note')
@ac_socket_requires(CaseAccessLevel.full_access)
def socket_ping_note(data):

    emit('ping-note', {"user": current_user.name, "note_id": data['note_id']}, room=data['channel'])


@socket_io.on('pong-note')
@ac_socket_requires(CaseAccessLevel.full_access)
def socket_pong_note(data):

    emit('pong-note', {"user": current_user.name, "note_id": data['note_id']}, room=data['channel'])


@socket_io.on('overview-map-note')
@ac_socket_requires(CaseAccessLevel.full_access)
def socket_overview_map_note(data):

    emit('overview-map-note', {"user": current_user.user, "note_id": data['note_id']}, room=data['channel'])


@socket_io.on('join-notes-overview')
@ac_socket_requires(CaseAccessLevel.full_access)
def socket_join_overview(data):

    room = data['channel']
    join_room(room=room)

    emit('join-notes-overview', {
        'message': f"{current_user.user} just joined",
        "user": current_user.user
    }, room=room)


@socket_io.on('disconnect')
@ac_socket_requires(CaseAccessLevel.full_access)
def socket_disconnect(data):
    emit('disconnect', current_user.user, broadcast=True)
