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
from flask_socketio import emit
from flask_socketio import join_room

from app import socket_io
from app import app
from app.iris_engine.access_control.iris_user import iris_current_user


def get_message(data):
    room = data['channel']
    join_room(room=room)

    emit('join', {'message': f"{iris_current_user.user} just joined", 'is_error': False}, room=room,
         namespace='/server-updates')


def socket_on_update_ping(msg):
    emit('update_ping', {'message': "Server connected", 'is_error': False},
         namespace='/server-updates')


def socket_on_update_do_reboot(msg):
    socket_io.emit('update_current_version', {"version": app.config.get('IRIS_VERSION')}, to='iris_update_status',
                   namespace='/server-updates')


def register_update_event_handlers():
    socket_io.on_event('join-update', get_message, namespace='/server-updates')
    socket_io.on_event('update_ping', socket_on_update_ping, namespace='/server-updates')
    socket_io.on_event('update_get_current_version', socket_on_update_do_reboot, namespace='/server-updates')
