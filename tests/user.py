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

from rest_api import RestApi
import requests
from urllib import parse


class User:

    def __init__(self, iris_url, login, api_key, identifier):
        self._iris_url = iris_url
        self._api = RestApi(iris_url, api_key)
        self._identifier = identifier
        self._login = login

    def get_identifier(self):
        return self._identifier

    def create(self, path, payload):
        return self._api.post(path, payload)

    def get(self, path):
        return self._api.get(path)

    def update(self, path, body):
        return self._api.put(path, body)

    def delete(self, path):
        return self._api.delete(path)

    def post_multipart_encoded_files(self, path, data, files):
        return self._api.post_multipart_encoded_files(path, data, files)

    def login(self, password):
        url = parse.urljoin(self._iris_url, '/api/v2/auth/login')
        return requests.post(url, json={'username': self._login, 'password': password})
