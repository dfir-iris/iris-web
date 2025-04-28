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
from flask_socketio import emit
from flask_socketio import join_room

from app import socket_io
from app.blueprints.access_controls import ac_socket_requires
from app.iris_engine.access_control.iris_user import iris_current_user
from app.models.authorization import CaseAccessLevel


@ac_socket_requires(CaseAccessLevel.full_access)
def socket_change_note(data):

    data['last_change'] = iris_current_user.user
    emit('change-note', data, to=data['channel'], skip_sid=request.sid, room=data['channel'])


@ac_socket_requires(CaseAccessLevel.full_access)
def socket_save_note(data):

    data['last_saved'] = iris_current_user.user
    emit('save-note', data, to=data['channel'], skip_sid=request.sid, room=data['channel'])


@ac_socket_requires(CaseAccessLevel.full_access)
def socket_clear_buffer_note(message):

    emit('clear_buffer-note', message, room=message['channel'])


@ac_socket_requires(CaseAccessLevel.full_access)
def socket_join_note(data):

    room = data['channel']
    join_room(room=room)

    emit('join-notes', {
        'message': f"{iris_current_user.user} just joined",
        "user": iris_current_user.user
    }, room=room)


@ac_socket_requires(CaseAccessLevel.full_access)
def socket_ping_note(data):

    emit('ping-note', {"user": iris_current_user.name, "note_id": data['note_id']}, room=data['channel'])


@ac_socket_requires(CaseAccessLevel.full_access)
def socket_pong_note(data):

    emit('pong-note', {"user": iris_current_user.name, "note_id": data['note_id']}, room=data['channel'])


@ac_socket_requires(CaseAccessLevel.full_access)
def socket_overview_map_note(data):

    emit('overview-map-note', {"user": iris_current_user.user, "note_id": data['note_id']}, room=data['channel'])


@ac_socket_requires(CaseAccessLevel.full_access)
def socket_join_overview(data):

    room = data['channel']
    join_room(room=room)

    emit('join-notes-overview', {
        'message': f"{iris_current_user.user} just joined",
        "user": iris_current_user.user
    }, room=room)


@ac_socket_requires(CaseAccessLevel.full_access)
def socket_disconnect(data):
    emit('disconnect', iris_current_user.user, broadcast=True)


def register_notes_event_handlers():
    socket_io.on_event('change-note', socket_change_note)
    socket_io.on_event('save-note', socket_save_note)
    socket_io.on_event('clear_buffer-note', socket_clear_buffer_note)
    socket_io.on_event('join-notes', socket_join_note)
    socket_io.on_event('ping-note', socket_ping_note)
    socket_io.on_event('pong-note', socket_pong_note)
    socket_io.on_event('overview-map-note', socket_overview_map_note)
    socket_io.on_event('join-notes-overview', socket_join_overview)
    socket_io.on_event('disconnect', socket_disconnect)
