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
import shutil
import time
from docker_compose import DockerCompose
from rest_api import RestApi
from server_timeout_error import ServerTimeoutError
from user import User

API_URL = 'http://127.0.0.1:8000'
_API_KEY = 'B8BA5D730210B50F41C06941582D7965D57319D5685440587F98DFDC45A01594'
_IRIS_PATH = Path('..')
_TEST_DATA_PATH = Path('./data')


class Iris:

    def __init__(self):
        self._docker_compose = DockerCompose(_IRIS_PATH, 'docker-compose.dev.yml')
        self._api = RestApi(API_URL, _API_KEY)
        self._administrator = User(API_URL, _API_KEY)

    def _wait(self, condition, attempts, sleep_duration=1):
        count = 0
        while not condition():
            time.sleep(sleep_duration)
            count += 1
            if count > attempts:
                print('Docker compose logs: ', self._docker_compose.extract_all_logs())
                raise ServerTimeoutError()

    def _wait_until_api_is_ready(self):
        self._wait(self._api.is_ready, 60)

    def start(self):
        # TODO it would be preferable to have a dedicated directory with the
        #      docker-compose.yml file, because for now, it will overwrite the
        #      .env file and development/tests contexts are mixed up. To do
        #      that, we should split the building phase of dockers from the
        #      execution phase of the docker-compose. We should minimize the
        #      docker-compose so that as few files as possible need to be
        #      copied. Also, we should try to use standard dockers as much as
        #      possible instead of having iris specific builds (for instance
        #      for the database)
        shutil.copy2(_TEST_DATA_PATH.joinpath('basic.env'), _IRIS_PATH.joinpath('.env'))
        self._docker_compose.start()
        print('Waiting for DFIR-IRIS to start...')
        self._wait_until_api_is_ready()

    def stop(self):
        self._docker_compose.stop()

    def create(self, path, body, query_parameters=None):
        return self._api.post(path, body, query_parameters)

    def get(self, path, query_parameters=None):
        return self._api.get(path, query_parameters=query_parameters)

    def delete(self, path):
        return self._api.delete(path)

    def get_api_version(self):
        return self._api.get('api/versions').json()

    def create_alert(self):
        body = {
            'alert_title': 'alert title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._api.post('/alerts/add', body)
        return response.json()

    def create_asset(self):
        body = {
            'asset_type_id': '9',
            'asset_name': 'admin_laptop',
        }
        response = self._api.post('/case/assets/add', body)
        return response.json()

    def create_user(self, user_name):
        body = {
            'user_name': user_name,
            'user_login': user_name,
            'user_email': f'{user_name}@aa.eu',
            'user_password': 'aA.1234567890'
        }
        user = self._api.post('/manage/users/add', body).json()
        return User(API_URL, user['data']['user_api_key'])

    def create_dummy_case(self):
        body = {
            'case_name': 'case name',
            'case_description': 'description',
            'case_customer': 1,
            'case_soc_id': ''
        }
        response = self._api.post('/api/v2/cases', body).json()
        return response['case_id']

    def update_case(self, case_identifier, data):
        response = self._api.post(f'/manage/cases/update/{case_identifier}', data)
        return response.json()

    def get_cases(self):
        return self._api.get('/manage/cases/list').json()

    def get_cases_filter(self):
        return self._api.get('/manage/cases/filter').json()

    def execute_graphql_query(self, payload):
        return self._administrator.execute_graphql_query(payload)

    def add_tasks(self, case_identifier, body):
        return self._api.post(f'/api/v2/cases/{case_identifier}/tasks',  body)

    def get_tasks(self, current_identifier):
        return self._api.get(f'/api/v2/tasks/{current_identifier}')

    def delete_tasks(self, current_identifier):
        return self._api.delete(f'/api/v2/tasks/{current_identifier}')
