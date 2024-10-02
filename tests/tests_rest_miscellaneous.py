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

    def test_get_api_version_should_not_fail(self):
        response = self._subject.get('api/versions').json()
        self.assertEqual('success', response['status'])

    def test_get_case_graph_should_not_fail(self):
        response = self._subject.get('/case/graph/getdata').json()
        self.assertEqual('success', response['status'])

    def test_create_case_template_should_not_be_forbidden_to_administrator(self):
        query_parameters = {
            'cid': 1
        }
        body = {
            'case_template_json': '{"name": "Template name"}',
        }
        response = self._subject.create('/manage/case-templates/add', body, query_parameters=query_parameters)
        # TODO should really be 201 here
        self.assertEqual(200, response.status_code)

    def test_update_settings_should_not_fail(self):
        body = {}
        response = self._subject.create('/manage/settings/update', body)
        self.assertEqual(200, response.status_code)

    def test_get_timeline_state_should_return_200(self):
        response = self._subject.get('/case/timeline/state', query_parameters={'cid': 1})
        self.assertEqual(200, response.status_code)
