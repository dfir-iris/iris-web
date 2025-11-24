#  IRIS Source Code
#  Copyright (C) 2023 - DFIR-IRIS
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

from socketio import SimpleClient


class SocketIOClient:

    def __init__(self, url, api_key):
        self._url = url
        self._api_key = api_key
        # Disable SSL verification for self-signed certs used in dev/test
        self._client = SimpleClient(ssl_verify=False)

    def connect(self):
        self._client.connect(self._url, headers={'Authorization': f'Bearer {self._api_key}'})

    def emit(self, event, channel):
        print(f'==> {event}/{channel}')
        self._client.emit(event, {'channel': channel})

    def receive(self):
        message = self._client.receive(timeout=20)
        print(f'<== {message[0]}/{message[1]}')
        return message[1]

    def disconnect(self):
        self._client.disconnect()
