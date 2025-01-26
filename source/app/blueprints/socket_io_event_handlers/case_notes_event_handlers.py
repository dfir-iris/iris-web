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

from flask import request
from flask_login import current_user
from flask_socketio import emit
from flask_socketio import join_room

from app import socket_io
from app.blueprints.access_controls import ac_socket_requires
from app.models.authorization import CaseAccessLevel


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
