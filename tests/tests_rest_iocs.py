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


class TestsRestIocs(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_get_ioc_should_not_fail(self):
        response = self._subject.get('/case/ioc/list').json()
        self.assertEqual('success', response['status'])

    def test_create_ioc_should_return_correct_ioc_type_id(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        self.assertEqual(1, response['ioc_type_id'])

    def test_get_ioc_should_return_ioc_type_id(self):
        ioc_type_id = 1
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': ioc_type_id, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        test = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        current_id = test['ioc_id']
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/iocs/{current_id}').json()
        self.assertEqual(ioc_type_id, response['ioc_type_id'])

    def test_get_ioc_with_missing_ioc_identifier_should_return_error(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        test = self._subject.get(f'/api/v2/cases/{case_identifier}/iocs/None').json()
        self.assertEqual('error', test['status'])

    def test_delete_ioc_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        ioc_identifier = response['ioc_id']
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}/iocs/{ioc_identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_ioc_with_missing_ioc_identifier_should_return_404(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}/iocs/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_get_iocs_should_not_fail(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/iocs')
        self.assertEqual(200, response.status_code)

    def test_create_ioc_should_add_the_ioc_in_the_correct_case(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/iocs').json()
        self.assertEqual(1, response['total'])

    def test_get_iocs_should_filter_and_return_ioc_type_identifier(self):
        case_identifier = self._subject.create_dummy_case()
        ioc_type_identifier = 2
        self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', {
            'ioc_type_id': ioc_type_identifier,
            'ioc_tlp_id': 2,
            'ioc_value': 'test_get_iocs_should_filter_on_ioc_value',
            'ioc_description': 'rewrw',
            'ioc_tags': '',
            'custom_attributes': {}
        }).json()
        self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', {
            'ioc_type_id': 1,
            'ioc_tlp_id': 2,
            'ioc_value': 'wrong_test',
            'ioc_description': 'rewrw',
            'ioc_tags': '',
            'custom_attributes': {}
        }).json()
        filters = {'ioc_value': 'test_get_iocs_should_filter_on_ioc_value'}
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/iocs',  query_parameters=filters).json()
        identifiers = []
        for ioc in response['data']:
            identifiers.append(ioc['ioc_type_id'])
        self.assertIn(ioc_type_identifier, identifiers)

    def test_get_ioc_should_return_404_when_not_present(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/iocs/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_get_ioc_should_return_200_on_success(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        ioc_identifier = response['ioc_id']
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/iocs/{ioc_identifier}')
        self.assertEqual(200, response.status_code)

    def test_get_iocs_should_include_tlp_information(self):
        case_identifier = self._subject.create_dummy_case()
        tlp_identifier = 2
        body = {'ioc_type_id': 1, 'ioc_tlp_id': tlp_identifier, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/iocs').json()
        self.assertEqual(tlp_identifier, response['data'][0]['tlp']['tlp_id'])

    def test_get_iocs_should_include_link_to_other_cases_with_same_value_type_ioc(self):
        case_identifier1 = self._subject.create_dummy_case()
        case_identifier2 = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        self._subject.create(f'/api/v2/cases/{case_identifier1}/iocs', body).json()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 1, 'ioc_value': '8.8.8.8', 'ioc_description': 'another', 'ioc_tags': ''}
        self._subject.create(f'/api/v2/cases/{case_identifier2}/iocs', body).json()
        response = self._subject.get(f'/api/v2/cases/{case_identifier2}/iocs').json()
        self.assertEqual(case_identifier1, response['data'][0]['link'][0]['case_id'])

    def test_create_ioc_should_include_field_link(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        self.assertEqual([], response['link'])

    def test_get_ioc_should_include_field_link(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        ioc_identifier = response['ioc_id']
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/iocs/{ioc_identifier}').json()
        self.assertEqual([], response['link'])

    def test_create_ioc_should_not_create_two_iocs_with_identical_type_and_value(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body)
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body)
        self.assertEqual(400, response.status_code)

    def test_delete_ioc_should_not_prevent_case_deletion(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        ioc_identifier = response['ioc_id']
        self._subject.create(f'/case/ioc/{ioc_identifier}/comments/add', {'comment_text': 'comment text'})
        self._subject.delete(f'/api/v2/cases/{case_identifier}/iocs/{ioc_identifier}')
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}')
        self.assertEqual(204, response.status_code)
        
    def test_update_ioc_should_not_fail(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        ioc_identifier = response['ioc_id']
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/iocs/{ioc_identifier}', {'ioc_value': '9.9.9.9'})
        self.assertEqual(200, response.status_code)

    def test_update_ioc_should_return_updated_value(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        ioc_identifier = response['ioc_id']
        new_value = '9.9.9.9'
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/iocs/{ioc_identifier}', {'ioc_value': new_value}).json()
        self.assertEqual(new_value, response['ioc_value'])

    def test_update_ioc_should_return_an_error_when_ioc_type_identifier_is_out_of_range(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        ioc_identifier = response['ioc_id']
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/iocs/{ioc_identifier}', {'ioc_type_id': '123456789'})
        self.assertEqual(400, response.status_code)

    def test_rest_case_should_return_error_ioc_when_permission_denied(self):
        user = self._subject.create_dummy_user()
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 1, 'ioc_value': 'IOC value'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body)
        response = user.get(f'/api/v2/cases/{case_identifier}/iocs')
        self.assertEqual(403, response.status_code)
