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

from time import sleep
from uuid import uuid4
from pathlib import Path
from docker_compose import DockerCompose
from rest_api import RestApi
from user import User
from socket_io_context_manager import SocketIOContextManager

API_URL = 'http://127.0.0.1:8000'
# TODO SSOT: this should be directly read from the .env file
_API_KEY = 'B8BA5D730210B50F41C06941582D7965D57319D5685440587F98DFDC45A01594'
_IRIS_PATH = Path('..')
_ADMINISTRATOR_USER_LOGIN = 'administrator'
ADMINISTRATOR_USER_IDENTIFIER = 1
_INITIAL_DEMO_CASE_IDENTIFIER = 1
IRIS_INITIAL_CUSTOMER_IDENTIFIER = 1

IRIS_PERMISSION_SERVER_ADMINISTRATOR = 0x2
IRIS_PERMISSION_ALERTS_READ = 0x4
IRIS_PERMISSION_ALERTS_WRITE = 0x8
IRIS_PERMISSION_ALERTS_DELETE = 0x10
IRIS_PERMISSION_CUSTOMERS_WRITE = 0x80

IRIS_CASE_ACCESS_LEVEL_READ_ONLY = 0x2
IRIS_CASE_ACCESS_LEVEL_FULL_ACCESS = 0x4

GROUP_ANALYSTS_IDENTIFIER = 2


class Iris:

    def __init__(self):
        self._docker_compose = DockerCompose(_IRIS_PATH, 'docker-compose.dev.yml')
        # TODO remove this field and use _administrator instead
        self._api = RestApi(API_URL, _API_KEY)
        self._administrator = User(API_URL, _ADMINISTRATOR_USER_LOGIN, _API_KEY, ADMINISTRATOR_USER_IDENTIFIER)
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

    def create_report(self, data, template_name):
        file_path = f'data/report_templates/{template_name}'
        with open(file_path, 'rb') as file:
            files = {'file': file}
            response = self._api.post_multipart_encoded_files('/manage/templates/add', data, files).json()
            return response['data']['report_id']

    def post_multipart_encoded_files(self, path, data, files):
        return self._api.post_multipart_encoded_files(path, data, files)

    def create_user(self, user_name, user_password):
        body = {
            'user_name': user_name,
            'user_login': user_name,
            'user_email': f'{user_name}@aa.eu',
            'user_password': user_password
        }
        user = self._api.post('/manage/users/add', body).json()
        return User(API_URL, user_name, user['data']['user_api_key'], user['data']['id'])

    def create_dummy_user(self, permissions = None):
        user = self.create_user(f'user{uuid4()}', 'aA.1234567890')
        if permissions:
            group_identifier = self.create_dummy_group(permissions)
            body = {'groups_membership': [group_identifier]}
            self.create(f'/manage/users/{user.get_identifier()}/groups/update', body)
        return user

    def create_dummy_group(self, permissions):
        group_name = f'group{uuid4()}'
        body = {
            'group_name': group_name,
            'group_description': f'Group description for {group_name}',
            'group_permissions': permissions
        }
        response = self.create('/manage/groups/add', body).json()
        return response['data']['group_id']

    def create_dummy_customer(self) -> int:
        response = self.create('/manage/customers/add', {'customer_name': f'customer{uuid4()}'}).json()
        return response['data']['customer_id']

    def create_dummy_case(self, customer_identifier=IRIS_INITIAL_CUSTOMER_IDENTIFIER):
        body = {
            'case_name': 'case name',
            'case_description': 'description',
            'case_customer_id': customer_identifier,
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
            if identifier == GROUP_ANALYSTS_IDENTIFIER:
                continue
            self.delete(f'/api/v2/manage/groups/{identifier}')
        response = self.get('api/v2/alerts').json()
        for alert in response['data']:
            identifier = alert['alert_id']
            self.delete(f'/api/v2/alerts/{identifier}')
        response = self.get('/global/tasks/list').json()
        for global_task in response['data']['tasks']:
            identifier = global_task['task_id']
            self.create(f'/global/tasks/delete/{identifier}', {})
        users = self.get('/manage/users/list').json()
        for user in users['data']:
            identifier = user['user_id']
            self.get(f'/manage/users/deactivate/{identifier}')
            self.delete(f'/api/v2/manage/users/{identifier}')
        body = {'customers_membership': [IRIS_INITIAL_CUSTOMER_IDENTIFIER]}
        self.create(f'/manage/users/{ADMINISTRATOR_USER_IDENTIFIER}/customers/update', body)
        customers = self.get('/manage/customers/list').json()
        for customer in customers['data']:
            identifier = customer['customer_id']
            self.create(f'/manage/customers/delete/{identifier}', {})

    def extract_logs(self, service):
        return self._docker_compose.extract_logs(service)

    def get_module_identifier_by_name(self, module_name):
        response = self.get('/manage/modules/list').json()
        module_identifier = None
        for module in response['data']:
            if module['module_human_name'] == module_name:
                module_identifier = module['id']
        return module_identifier

    @staticmethod
    def get_most_recent_object_history_entry(response):
        modification_history = response['modification_history']
        current_timestamp = 0
        result = None
        for timestamp_as_string, modification in modification_history.items():
            timestamp = float(timestamp_as_string)
            if timestamp < current_timestamp:
                continue
            result = modification
            current_timestamp = timestamp
        return result

    def wait_for_module_task(self):
        response = self.get('/dim/tasks/list/1').json()
        attempts = 0
        while len(response['data']) == 0:
            sleep(1)
            response = self.get('/dim/tasks/list/1').json()
            attempts += 1
            if attempts > 20:
                logs = self.extract_logs('worker')
                raise TimeoutError(f'Timed out with logs: {logs}')
        return response['data'][0]

    def get_latest_activity(self):
        activities = self.get('/activities/list-all').json()
        return activities['data'][0]
