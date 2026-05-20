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
from iris import ADMINISTRATOR_USER_IDENTIFIER


class TestsRestGlobalTasks(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_create_global_task_should_return_201(self):
        body = {'task_title': 'dummy title', 'task_status_id': 1, 'task_assignee_id': ADMINISTRATOR_USER_IDENTIFIER}
        response = self._subject.create('/api/v2/global-tasks', body)
        self.assertEqual(201, response.status_code)

    def test_create_global_task_should_set_field_task_close_date(self):
        closing_date = '2025-11-19T12:28:01'
        body = {'task_title': 'new title', 'task_status_id': 1, 'task_assignee_id': ADMINISTRATOR_USER_IDENTIFIER,
                'task_close_date': closing_date}
        response = self._subject.create('/api/v2/global-tasks', body).json()
        self.assertEqual(closing_date, response['task_close_date'])

    def test_get_global_task_should_return_200(self):
        body = {'task_title': 'dummy title', 'task_status_id': 1, 'task_assignee_id': ADMINISTRATOR_USER_IDENTIFIER}
        response = self._subject.create('/api/v2/global-tasks', body).json()
        identifier = response['task_id']
        response = self._subject.get(f'/api/v2/global-tasks/{identifier}')
        self.assertEqual(200, response.status_code)

    def test_get_global_task_should_return_field_task_id(self):
        body = {'task_title': 'dummy title', 'task_status_id': 1, 'task_assignee_id': ADMINISTRATOR_USER_IDENTIFIER}
        response = self._subject.create('/api/v2/global-tasks', body).json()
        identifier = response['task_id']
        response = self._subject.get(f'/api/v2/global-tasks/{identifier}').json()
        self.assertEqual(identifier, response['task_id'])

    def test_delete_global_task_should_return_204(self):
        body = {'task_title': 'dummy title', 'task_status_id': 1, 'task_assignee_id': ADMINISTRATOR_USER_IDENTIFIER}
        response = self._subject.create('/api/v2/global-tasks', body).json()
        identifier = response['task_id']
        response = self._subject.delete(f'/api/v2/global-tasks/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_get_global_task_should_return_404_when_deleted(self):
        body = {'task_title': 'dummy title', 'task_status_id': 1, 'task_assignee_id': ADMINISTRATOR_USER_IDENTIFIER}
        response = self._subject.create('/api/v2/global-tasks', body).json()
        identifier = response['task_id']
        self._subject.delete(f'/api/v2/global-tasks/{identifier}')
        response = self._subject.get(f'/api/v2/global-tasks/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_update_global_task_should_return_200(self):
        body = {'task_title': 'dummy title', 'task_status_id': 1, 'task_assignee_id': ADMINISTRATOR_USER_IDENTIFIER}
        response = self._subject.create('/api/v2/global-tasks', body).json()
        identifier = response['task_id']
        body = {'task_title': 'new title', 'task_status_id': 1, 'task_assignee_id': ADMINISTRATOR_USER_IDENTIFIER}
        response = self._subject.update(f'/api/v2/global-tasks/{identifier}', body)
        self.assertEqual(200, response.status_code)

    def test_update_global_task_should_update_field_task_close_date(self):
        body = {'task_title': 'dummy title', 'task_status_id': 1, 'task_assignee_id': ADMINISTRATOR_USER_IDENTIFIER}
        response = self._subject.create('/api/v2/global-tasks', body).json()
        identifier = response['task_id']
        closing_date = '2025-11-19T12:28:01'
        body = {'task_title': 'new title', 'task_status_id': 1, 'task_assignee_id': ADMINISTRATOR_USER_IDENTIFIER,
                'task_close_date': closing_date}
        response = self._subject.update(f'/api/v2/global-tasks/{identifier}', body).json()
        self.assertEqual(closing_date, response['task_close_date'])

    def test_search_global_tasks_should_return_200(self):
        response = self._subject.get('/api/v2/global-tasks')
        self.assertEqual(200, response.status_code)

    def test_search_global_tasks_should_return_total(self):
        body = {'task_title': 'dummy title', 'task_status_id': 1, 'task_assignee_id': ADMINISTRATOR_USER_IDENTIFIER}
        response = self._subject.create('/api/v2/global-tasks', body).json()
        response = self._subject.get('/api/v2/global-tasks').json()
        self.assertEqual(1, response['total'])
