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
        body = {'task_assignees_id': [1], 'task_description': '', 'task_status_id': 1, 'task_tags': '',
                'task_title': 'dummy title', 'custom_attributes': {}}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body)
        self.assertEqual(201, response.status_code)

    def test_add_task_with_missing_task_title_identifier_should_return_400(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [1], 'task_description': '', 'task_status_id': 1, 'task_tags': '',
                'custom_attributes': {}}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body)
        self.assertEqual(400, response.status_code)

    def test_create_case_with_spurious_slash_should_return_404(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [1], 'task_description': '', 'task_status_id': 1, 'task_tags': '',
                'task_title': 'dummy title', 'custom_attributes': {}}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks/', body)
        self.assertEqual(404, response.status_code)

    def test_get_task_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [2], 'task_description': '', 'task_status_id': 1, 'task_tags': '',
                'task_title': 'dummy title',
                'custom_attributes': {}}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        task_identifier = response['id']
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/tasks/{task_identifier}')
        self.assertEqual(200, response.status_code)

    def test_get_task_with_missing_task_identifier_should_return_error(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [1], 'task_description': '', 'task_status_id': 1, 'task_tags': '',
                'task_title': 'dummy title', 'custom_attributes': {}}
        self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body)
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/tasks/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_delete_task_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [1], 'task_description': '', 'task_status_id': 1, 'task_tags': '',
                'task_title': 'dummy title',
                'custom_attributes': {}}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        task_identifier = response['id']
        test = self._subject.delete(f'/api/v2/cases/{case_identifier}/tasks/{task_identifier}')
        self.assertEqual(204, test.status_code)

    def test_delete_task_with_missing_task_identifier_should_return_404(self):
        case_identifier = self._subject.create_dummy_case()
        task_id = 1
        body = {'task_assignees_id': [task_id], 'task_description': '', 'task_status_id': 1, 'task_tags': '', 'task_title': 'dummy title',
                'custom_attributes': {}}
        self._subject.create(f'/api/v2/cases/{case_identifier}/tasks',  body)
        test = self._subject.delete(f'/api/v2/cases/{case_identifier}/tasks/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, test.status_code)
