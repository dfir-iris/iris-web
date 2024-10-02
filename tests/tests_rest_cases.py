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


def _get_case_with_identifier(response, identifier):
    for case in response['cases']:
        if identifier == case['case_id']:
            return case
    raise ValueError('Case not found')


class TestsRestCases(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_manage_case_filter_api_rest_should_fail(self):
        self._subject.create_dummy_case()
        response = self._subject.get('/manage/cases/filter').json()
        self.assertEqual('success', response['status'])

    def test_get_cases_should_not_fail(self):
        response = self._subject.get('/api/v2/cases')
        self.assertEqual(200, response.status_code)

    def test_get_cases_should_filter_on_case_name(self):
        response = self._subject.create('/api/v2/cases', {
            'case_name': 'test_get_cases_should_filter_on_case_name',
            'case_description': 'description',
            'case_customer': 1,
            'case_soc_id': ''
        }).json()
        case_identifier = response['case_id']
        filters = {'case_name': 'test_get_cases_should_filter_on_case_name'}
        response = self._subject.get('/api/v2/cases', query_parameters=filters).json()
        identifiers = []
        for case in response['cases']:
            identifiers.append(case['case_id'])
        self.assertIn(case_identifier, identifiers)

    def test_get_cases_should_filter_on_is_open(self):
        case_identifier = self._subject.create_dummy_case()
        self._subject.create(f'/manage/cases/close/{case_identifier}', {})
        filters = {'is_open': 'true'}
        response = self._subject.get('/api/v2/cases', query_parameters=filters).json()
        identifiers = []
        for case in response['cases']:
            identifiers.append(case['case_id'])
        self.assertNotIn(case_identifier, identifiers)

    def test_get_cases_should_return_the_state_name(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get('/api/v2/cases').json()
        case = _get_case_with_identifier(response, case_identifier)
        self.assertEqual('Open', case['state']['state_name'])

    def test_get_cases_should_return_the_owner_name(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get('/api/v2/cases').json()
        case = _get_case_with_identifier(response, case_identifier)
        self.assertEqual('administrator', case['owner']['user_name'])

    def test_get_case_should_have_field_case_name(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}').json()
        self.assertIn('case_name', response)

    def test_create_case_should_return_data_with_case_customer_when_case_customer_is_an_empty_string(self):
        body = {
            'case_name': 'case name',
            'case_description': 'description',
            'case_customer': '',
            'case_soc_id': ''
        }
        response = self._subject.create('/api/v2/cases', body).json()
        self.assertIn('case_customer', response['data'])
