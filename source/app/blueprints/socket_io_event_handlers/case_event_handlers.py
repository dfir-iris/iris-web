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
def socket_summary_onchange(data):

    data['last_change'] = iris_current_user.user
    emit('change', data, to=data['channel'], skip_sid=request.sid)


@ac_socket_requires(CaseAccessLevel.full_access)
def socket_summary_onsave(data):

    data['last_saved'] = iris_current_user.user
    emit('save', data, to=data['channel'], skip_sid=request.sid)


@ac_socket_requires(CaseAccessLevel.full_access)
def socket_summary_on_clear_buffer(message):

    emit('clear_buffer', message)


@ac_socket_requires(CaseAccessLevel.full_access)
def get_message(data):

    room = data['channel']
    join_room(room=room)
    emit('join', {'message': f"{iris_current_user.user} just joined"}, room=room)


@ac_socket_requires(CaseAccessLevel.full_access)
def socket_join_case_obj_notif(data):
    room = data['channel']
    join_room(room=room)


def register_case_event_handlers():
    socket_io.on_event('change', socket_summary_onchange)
    socket_io.on_event('save', socket_summary_onsave)
    socket_io.on_event('clear_buffer', socket_summary_on_clear_buffer)
    socket_io.on_event('join', get_message)
    socket_io.on_event('join-case-obj-notif', socket_join_case_obj_notif)
