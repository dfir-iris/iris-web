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

from unittest import TestCase
from iris import Iris

_IDENTIFIER_FOR_NONEXISTENT_OBJECT = 123456789


class TestsRestTasks(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_add_task_should_return_201(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_description': '', 'task_status_id': 1, 'task_tags': '',
                'task_title': 'dummy title', 'custom_attributes': {}}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body)
        self.assertEqual(201, response.status_code)

    def test_add_task_with_missing_task_title_identifier_should_return_400(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_description': '', 'task_status_id': 1, 'task_tags': '',
                'custom_attributes': {}}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body)
        self.assertEqual(400, response.status_code)

    def test_create_case_with_spurious_slash_should_return_404(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_description': '', 'task_status_id': 1, 'task_tags': '',
                'task_title': 'dummy title', 'custom_attributes': {}}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks/', body)
        self.assertEqual(404, response.status_code)

    def test_get_task_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_description': '', 'task_status_id': 1, 'task_tags': '',
                'task_title': 'dummy title',
                'custom_attributes': {}}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        task_identifier = response['id']
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/tasks/{task_identifier}')
        self.assertEqual(200, response.status_code)

    def test_get_task_with_missing_task_identifier_should_return_error(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_description': '', 'task_status_id': 1, 'task_tags': '',
                'task_title': 'dummy title', 'custom_attributes': {}}
        self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body)
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/tasks/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_delete_task_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_description': '', 'task_status_id': 1, 'task_tags': '',
                'task_title': 'dummy title',
                'custom_attributes': {}}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        task_identifier = response['id']
        test = self._subject.delete(f'/api/v2/cases/{case_identifier}/tasks/{task_identifier}')
        self.assertEqual(204, test.status_code)

    def test_delete_task_with_missing_task_identifier_should_return_404(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_description': '', 'task_status_id': 1, 'task_tags': '', 'task_title': 'dummy title',
                'custom_attributes': {}}
        self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body)
        test = self._subject.delete(f'/api/v2/cases/{case_identifier}/tasks/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, test.status_code)

    def test_get_user_task_should_not_fail(self):
        case_identifier = self._subject.create_dummy_case()
        user = self._subject.create_dummy_user()
        body = {'task_assignees_id': [user.get_identifier()], 'task_description': '', 'task_status_id': 1, 'task_tags': '', 'task_title': 'dummy title',
                'custom_attributes': {}}
        self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body)
        response = user.get('/user/tasks/list')
        self.assertEqual(200, response.status_code)

    def test_get_user_task_should_contain_task_case_field(self):
        case_identifier = self._subject.create_dummy_case()
        user = self._subject.create_dummy_user()
        body = {'task_assignees_id': [user.get_identifier()], 'task_description': '', 'task_status_id': 1, 'task_tags': '', 'task_title': 'dummy title',
                'custom_attributes': {}}
        self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body)
        response = user.get('/user/tasks/list').json()
        self.assertEqual(f'#{case_identifier} - case name', response['data']['tasks'][0]['task_case'])

    def test_update_task_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'dummy title'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        identifier = response['id']
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/tasks/{identifier}',
                                        {'task_title': 'new title', 'task_status_id': 1, 'task_assignees_id': []})
        self.assertEqual(200, response.status_code)

    def test_update_task_should_update_assignees(self):
        case_identifier = self._subject.create_dummy_case()
        user = self._subject.create_dummy_user()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'dummy title'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        identifier = response['id']
        self._subject.update(f'/api/v2/cases/{case_identifier}/tasks/{identifier}',
                             {'task_title': 'dummy title', 'task_status_id': 1, 'task_assignees_id': [user.get_identifier()]})
        response = self._subject.get('/case/tasks/list', query_parameters={'cid': case_identifier}).json()
        self.assertEqual(user.get_identifier(), response['data']['tasks'][0]['task_assignees'][0]['id'])

    def test_update_task_without_task_status_id_should_return_400(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'dummy title'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        identifier = response['id']
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/tasks/{identifier}',
                                        {'task_title': 'new title', 'task_assignees_id': []})
        self.assertEqual(400, response.status_code)

    def test_update_task_should_return_a_task(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'dummy title'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        identifier = response['id']
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/tasks/{identifier}',
                                        {'task_title': 'new title', 'task_status_id': 1, 'task_assignees_id': []}).json()
        self.assertEqual('new title', response['task_title'])

    def test_update_task_should_update_status_id(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'dummy title'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        identifier = response['id']
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/tasks/{identifier}',
                                        {'task_title': 'dummy title', 'task_status_id': 2, 'task_assignees_id': []}).json()
        self.assertEqual(2, response['task_status_id'])

    def test_get_tasks_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/tasks')
        self.assertEqual(200, response.status_code)

    def test_get_tasks_should_return_empty_list_for_field_data_when_there_are_no_tasks(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/tasks').json()
        self.assertEqual([], response['data'])

    def test_get_tasks_should_return_total(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'dummy title'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/tasks').json()
        self.assertEqual(1, response['total'])

    def test_get_tasks_should_honour_per_page_pagination_parameter(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'task1'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'task2'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'task3'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/tasks', {'per_page': 2}).json()
        self.assertEqual(2, len(response['data']))

    def test_get_tasks_should_return_current_page(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'task1'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'task2'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'task3'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/tasks', {'page': 2, 'per_page': 2}).json()
        self.assertEqual(2, response['current_page'])

    def test_get_tasks_should_return_correct_task_uuid(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'title'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        identifier = response['id']
        response = self._subject.get(f'/api/v2/tasks/{identifier}').json()
        expected_uuid = response['task_uuid']
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/tasks').json()
        self.assertEqual(expected_uuid, response['data'][0]['task_uuid'])
