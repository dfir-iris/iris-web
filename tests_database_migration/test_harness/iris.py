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

from uuid import uuid4
from pathlib import Path
from test_harness.rest_api import RestApi
from test_harness.user import User
from test_harness.socket_io_context_manager import SocketIOContextManager

API_URL = 'http://127.0.0.1:8000'
# TODO SSOT: this should be directly read from the .env file
_API_KEY = 'B8BA5D730210B50F41C06941582D7965D57319D5685440587F98DFDC45A01594'
_IRIS_PATH = Path('../..')
_ADMINISTRATOR_USER_IDENTIFIER = 1
_INITIAL_DEMO_CASE_IDENTIFIER = 1


class Iris:

    def __init__(self):
        # TODO remove this field and use _administrator instead
        self._api = RestApi(API_URL, _API_KEY)
        self._administrator = User(API_URL, _API_KEY, _ADMINISTRATOR_USER_IDENTIFIER)
        self._socket_io_client = SocketIOContextManager(API_URL, _API_KEY)

    def get_socket_io_client(self) -> SocketIOContextManager:
        return self._socket_io_client

    def create(self, path, body, query_parameters=None):
        return self._api.post(path, body, query_parameters)

    def get(self, path, query_parameters=None):
        return self._api.get(path, query_parameters=query_parameters)

    def update(self, path, body):
        return self._api.put(path, body)

    def delete(self, path):
        return self._api.delete(path)

    def post_multipart_encoded_file(self, path, data, file_path):
        return self._api.post_multipart_encoded_file(path, data, file_path)

    def create_user(self, user_name, user_password):
        body = {
            'user_name': user_name,
            'user_login': user_name,
            'user_email': f'{user_name}@aa.eu',
            'user_password': user_password
        }
        user = self._api.post('/manage/users/add', body).json()
        return User(API_URL, user['data']['user_api_key'], user['data']['id'])

    def create_dummy_user(self):
        return self.create_user(f'user{uuid4()}', 'aA.1234567890')

    def create_dummy_case(self):
        body = {
            'case_name': 'case name',
            'case_description': 'description',
            'case_customer_id': 1,
            'case_soc_id': ''
        }
        response = self._api.post('/api/v2/cases', body).json()
        return response['case_id']

    def execute_graphql_query(self, payload):
        return self._administrator.execute_graphql_query(payload)

    def clear_database(self):
        cases = self.get('/api/v2/cases', query_parameters={'per_page': 1000000000}).json()
        for case in cases['data']:
            identifier = case['case_id']
            if identifier == _INITIAL_DEMO_CASE_IDENTIFIER:
                continue
            self.delete(f'/api/v2/cases/{identifier}')
        groups = self.get('/manage/groups/list').json()
        for group in groups['data']:
            identifier = group['group_id']
            self.create(f'/manage/groups/delete/{identifier}', {})
        users = self.get('/manage/users/list').json()
        for user in users['data']:
            identifier = user['user_id']
            self.get(f'/manage/users/deactivate/{identifier}')
            self.create(f'/manage/users/delete/{identifier}', {})
