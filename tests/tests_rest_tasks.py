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


class TestsRest(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_get_task_should_return_403_when_user_has_insufficient_rights(self):
        case_identifier = self._subject.create_dummy_case()
        user = self._subject.create_dummy_user()
        body = {'task_assignees_id': [1], 'task_description': '', 'task_status_id': 1, 'task_tags': '', 'task_title': 'dummy title', 'custom_attributes': {}}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks',  body).json()
        task_identifier = response['id']
        body = {
            'cases_list': [_INITIAL_DEMO_CASE_IDENTIFIER],
            'access_level': _CASE_ACCESS_LEVEL_FULL_ACCESS
        }
        self._subject.create(f'/manage/users/{user.get_identifier()}/cases-access/update', body)

        response = user.get(f'/api/v2/tasks/{task_identifier}')
        self.assertEqual(403, response.status_code)

    def test_delete_task_should_return_403_when_user_has_insufficient_rights(self):
        case_identifier = self._subject.create_dummy_case()
        user = self._subject.create_dummy_user()
        body = {'task_assignees_id': [1], 'task_description': '', 'task_status_id': 1, 'task_tags': '', 'task_title': 'dummy title', 'custom_attributes': {}}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks',  body).json()
        task_identifier = response['id']
        body = {
            'cases_list': [_INITIAL_DEMO_CASE_IDENTIFIER],
            'access_level': _CASE_ACCESS_LEVEL_FULL_ACCESS
        }
        self._subject.create(f'/manage/users/{user.get_identifier()}/cases-access/update', body)

        response = user.delete(f'/api/v2/tasks/{task_identifier}')
        self.assertEqual(403, response.status_code)
