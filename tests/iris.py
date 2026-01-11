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

from pathlib import Path
from docker_compose import DockerCompose
from rest_api import RestApi
from user import User
from uuid import uuid4

API_URL = 'http://127.0.0.1:8000'
# TODO SSOT: this could be directly read from the .env file
_API_KEY = 'B8BA5D730210B50F41C06941582D7965D57319D5685440587F98DFDC45A01594'
_IRIS_PATH = Path('..')
_TEST_DATA_PATH = Path('./data')
_ADMINISTRATOR_USER_IDENTIFIER = 1
_INITIAL_DEMO_CASE_IDENTIFIER = 1


class Iris:

    def __init__(self):
        self._docker_compose = DockerCompose(_IRIS_PATH, 'docker-compose.dev.yml')
        # TODO remove this field and use _administrator instead
        self._api = RestApi(API_URL, _API_KEY)
        self._administrator = User(API_URL, _API_KEY, _ADMINISTRATOR_USER_IDENTIFIER)

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

    def post_multipart_encoded_files(self, path, data, files):
        return self._api.post_multipart_encoded_files(path, data, files)

    def _create_user(self, user_name):
        body = {
            'user_name': user_name,
            'user_login': user_name,
            'user_email': f'{user_name}@aa.eu',
            'user_password': 'aA.1234567890'
        }
        user = self._api.post('/manage/users/add', body).json()
        return User(API_URL, user['data']['user_api_key'], user['data']['id'])

    def create_dummy_user(self):
        return self._create_user(f'user{uuid4()}')

    def create_dummy_case(self):
        body = {
            'case_name': 'case name',
            'case_description': 'description',
            'case_customer': 1,
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
