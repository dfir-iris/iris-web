#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
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


class TestsRestModuleTasks(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_get_module_tasks_should_return_case_identifier(self):
        case_identifier = self._subject.create_dummy_case()

        module_identifier = self._subject.get_module_identifier_by_name('IrisCheck')
        self._subject.create(f'/manage/modules/enable/{module_identifier}', {})
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body)
        self._subject.create(f'/manage/modules/disable/{module_identifier}', {})

        response = self._subject.get('/dim/tasks/list/1').json()
        self.assertEqual(f'Case #{case_identifier}', response['data'][0]['case'])
