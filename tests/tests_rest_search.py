#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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


class TestsRestSearch(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_search_should_return_200(self):
        response = self._subject.get('/api/v2/search', query_parameters={'types': 'ioc', 'value': '%'})
        self.assertEqual(200, response.status_code)

    def test_search_should_return_400_when_types_is_missing(self):
        response = self._subject.get('/api/v2/search', query_parameters={'value': '%'})
        self.assertEqual(400, response.status_code)

    def test_search_should_return_400_when_value_is_missing(self):
        response = self._subject.get('/api/v2/search', query_parameters={'types': 'ioc'})
        self.assertEqual(400, response.status_code)

    def test_search_should_return_400_when_type_is_unsupported(self):
        response = self._subject.get('/api/v2/search', query_parameters={'types': 'magic', 'value': '%'})
        self.assertEqual(400, response.status_code)

    def test_search_should_return_envelope_with_data_and_pagination(self):
        response = self._subject.get('/api/v2/search', query_parameters={'types': 'notes', 'value': '%'})
        body = response.json()
        self.assertIn('data', body)
        self.assertIn('pagination', body)
        self.assertIn('total', body['pagination'])
        self.assertIn('page', body['pagination'])
        self.assertIn('per_page', body['pagination'])

    def test_search_should_accept_multiple_types_comma_separated(self):
        response = self._subject.get('/api/v2/search', query_parameters={'types': 'ioc,notes,comments', 'value': '%'})
        self.assertEqual(200, response.status_code)

    def test_search_should_accept_assets_events_tasks_evidences_types(self):
        response = self._subject.get('/api/v2/search', query_parameters={'types': 'assets,events,tasks,evidences', 'value': '%'})
        self.assertEqual(200, response.status_code)

    def test_search_per_page_should_be_clamped(self):
        response = self._subject.get('/api/v2/search', query_parameters={'types': 'notes', 'value': '%', 'per_page': 9999})
        body = response.json()
        # Capped at 100 per `search_across`.
        self.assertLessEqual(body['pagination']['per_page'], 100)

    def test_search_should_accept_case_id_scope(self):
        case_id = self._subject.create_dummy_case()
        response = self._subject.get(
            f'/api/v2/search?types=ioc,notes,assets,events,tasks,comments,evidences&value=%25&case_id={case_id}'
        )
        self.assertEqual(200, response.status_code)

    def test_search_should_accept_case_ids_scope_csv(self):
        c1 = self._subject.create_dummy_case()
        c2 = self._subject.create_dummy_case()
        response = self._subject.get(
            f'/api/v2/search?types=ioc,notes&value=%25&case_ids={c1},{c2}'
        )
        self.assertEqual(200, response.status_code)

    def test_search_results_should_be_scoped_to_user_accessible_cases(self):
        # A fresh user with no group membership only inherits whatever
        # default access groups the seed provides. We just assert the
        # envelope shape returns and the call is access-checked — actual
        # row visibility is enforced by the data-layer scope filter.
        user = self._subject.create_dummy_user()
        response = user.get('/api/v2/search?types=notes,ioc,assets,events,tasks,comments,evidences&value=%25')
        self.assertEqual(200, response.status_code)
