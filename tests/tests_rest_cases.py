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
    for case in response['data']:
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

    def test_create_case_should_return_201(self):
        response = self._subject.create('/api/v2/cases', {
            'case_name': 'name',
            'case_description': 'description',
            'case_customer_id': 1,
            'case_soc_id': ''
        })
        self.assertEqual(201, response.status_code)

    def test_create_case_with_spurious_slash_should_return_404(self):
        response = self._subject.create('/api/v2/cases/', {
            'case_name': 'name',
            'case_description': 'description',
            'case_customer_id': 1,
            'case_soc_id': ''
        })
        self.assertEqual(404, response.status_code)

    def test_create_case_with_missing_name_should_return_400(self):
        response = self._subject.create('/api/v2/cases', {
            'case_description': 'description',
            'case_customer_id': 1,
            'case_soc_id': ''
        })
        self.assertEqual(400, response.status_code)

    def test_create_case_with_classification_id_should_set_classification_id(self):
        response = self._subject.create('/api/v2/cases', {
            'case_name': 'name',
            'case_description': 'description',
            'case_customer_id': 1,
            'case_soc_id': '',
            'classification_id': 2
        }).json()
        self.assertEqual(2, response['classification_id'])

    def test_create_case_should_add_a_new_case(self):
        response = self._subject.get('/api/v2/cases').json()
        initial_case_count = len(response['data'])
        self._subject.create_dummy_case()
        response = self._subject.get('/api/v2/cases').json()
        case_count = len(response['data'])
        self.assertEqual(initial_case_count + 1, case_count)

    def test_get_case_should_return_case_data(self):
        response = self._subject.create('/api/v2/cases', {
            'case_name': 'name',
            'case_description': 'description',
            'case_customer_id': 1,
            'case_soc_id': ''
        }).json()
        identifier = response['case_id']
        response = self._subject.get(f'/api/v2/cases/{identifier}').json()
        self.assertEqual('description', response['case_description'])

    def test_delete_case_should_return_204(self):
        response = self._subject.create('/api/v2/cases', {
            'case_name': 'name',
            'case_description': 'description',
            'case_customer_id': 1,
            'case_soc_id': ''
        }).json()
        identifier = response['case_id']
        response = self._subject.delete(f'/api/v2/cases/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_get_case_should_return_404_after_it_is_deleted(self):
        response = self._subject.create('/api/v2/cases', {
            'case_name': 'name',
            'case_description': 'description',
            'case_customer_id': 1,
            'case_soc_id': ''
        }).json()
        identifier = response['case_id']
        self._subject.delete(f'/api/v2/cases/{identifier}')
        response = self._subject.get(f'/api/v2/cases/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_update_case_should_not_require_case_name_issue_358(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/manage/cases/update/{case_identifier}', {'case_tags': 'test,example'}).json()
        self.assertEqual('success', response['status'])

    def test_get_cases_should_not_fail(self):
        response = self._subject.get('/api/v2/cases')
        self.assertEqual(200, response.status_code)

    def test_get_cases_should_filter_on_case_name(self):
        response = self._subject.create('/api/v2/cases', {
            'case_name': 'test_get_cases_should_filter_on_case_name',
            'case_description': 'description',
            'case_customer_id': 1,
            'case_soc_id': ''
        }).json()
        case_identifier = response['case_id']
        filters = {'case_name': 'test_get_cases_should_filter_on_case_name'}
        response = self._subject.get('/api/v2/cases', query_parameters=filters).json()
        identifiers = []
        for case in response['data']:
            identifiers.append(case['case_id'])
        self.assertIn(case_identifier, identifiers)

    def test_get_cases_should_filter_on_is_open(self):
        case_identifier = self._subject.create_dummy_case()
        self._subject.create(f'/manage/cases/close/{case_identifier}', {})
        filters = {'is_open': 'true'}
        response = self._subject.get('/api/v2/cases', query_parameters=filters).json()
        identifiers = []
        for case in response['data']:
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

    def test_get_case_should_have_field_case_customer_id(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}').json()
        self.assertIn('case_customer_id', response)

    def test_create_case_should_return_data_with_case_customer_when_case_customer_is_an_empty_string(self):
        body = {
            'case_name': 'case name',
            'case_description': 'description',
            'case_customer_id': '',
            'case_soc_id': ''
        }
        response = self._subject.create('/api/v2/cases', body).json()
        self.assertIn('case_customer_id', response['data'])

    def test_create_case_should_return_field_case_customer(self):
        body = {
            'case_name': 'case name',
            'case_description': 'description',
            'case_customer_id': 1,
            'case_soc_id': ''
        }
        response = self._subject.create('/api/v2/cases', body).json()
        self.assertEqual(1, response['case_customer']['customer_id'])

    def test_update_case_should_return_200(self):
        identifier = self._subject.create_dummy_case()
        response = self._subject.update(f'/api/v2/cases/{identifier}', {'case_name': 'new name'})
        self.assertEqual(200, response.status_code)

    def test_update_case_should_allow_to_update_severity(self):
        identifier = self._subject.create_dummy_case()
        response = self._subject.update(f'/api/v2/cases/{identifier}', {'severity_id': 5}).json()
        self.assertEqual(5, response['severity_id'])

    def test_update_case_should_allow_to_update_classification(self):
        identifier = self._subject.create_dummy_case()
        response = self._subject.update(f'/api/v2/cases/{identifier}', {'classification_id': 3}).json()
        self.assertEqual(3, response['classification_id'])

    def test_update_case_should_allow_to_update_owner(self):
        user = self._subject.create_dummy_user()
        identifier = self._subject.create_dummy_case()
        response = self._subject.update(f'/api/v2/cases/{identifier}', {'owner_id': user.get_identifier()}).json()
        self.assertEqual(user.get_identifier(), response['owner']['id'])

    def test_update_case_should_allow_to_update_state(self):
        identifier = self._subject.create_dummy_case()
        response = self._subject.update(f'/api/v2/cases/{identifier}', {'state_id': 2}).json()
        self.assertEqual(2, response['state']['state_id'])

    def test_update_case_should_allow_to_update_status(self):
        identifier = self._subject.create_dummy_case()
        response = self._subject.update(f'/api/v2/cases/{identifier}', {'status_id': 2}).json()
        self.assertEqual(2, response['status_id'])

    def test_update_case_should_allow_to_update_customer(self):
        identifier = self._subject.create_dummy_case()
        customer_identifier = self._subject.create_dummy_customer()
        response = self._subject.update(f'/api/v2/cases/{identifier}', {'case_customer_id': customer_identifier}).json()
        self.assertEqual(customer_identifier, response['case_customer_id'])

    def test_update_case_should_allow_to_update_reviewer(self):
        identifier = self._subject.create_dummy_case()
        user = self._subject.create_dummy_user()
        response = self._subject.update(f'/api/v2/cases/{identifier}', {'reviewer_id': user.get_identifier()}).json()
        self.assertEqual(user.get_identifier(), response['reviewer_id'])

    def test_update_case_should_allow_to_update_tags(self):
        identifier = self._subject.create_dummy_case()
        response = self._subject.update(f'/api/v2/cases/{identifier}', {'case_tags': 'tag1,tag2'}).json()
        self.assertEqual('tag1,tag2', response['case_tags'])

    def test_update_case_should_return_invalid_integer_on_case_severity_update(self):
        identifier = self._subject.create_dummy_case()
        response = self._subject.update(f'/api/v2/cases/{identifier}', {'severity_id': 'invalid_integer'})
        self.assertEqual(400, response.status_code)
        self.assertEqual(['Not a valid integer.'], response.json()['data']['severity_id'])

    def test_close_case_should_set_closing_date(self):
        identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/manage/cases/close/{identifier}', {}).json()
        self.assertIsNotNone(response['data']['close_date'])
