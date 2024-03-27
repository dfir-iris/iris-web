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
from iris import API_URL
from graphql_api import GraphQLApi
from base64 import b64encode


class Tests(TestCase):

    _subject = None

    @classmethod
    def setUpClass(cls) -> None:
        cls._subject = Iris()
        cls._subject.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._subject.stop()

    def test_create_asset_should_not_fail(self):
        response = self._subject.create_asset()
        self.assertEqual('success', response['status'])

    def test_get_api_version_should_not_fail(self):
        response = self._subject.get_api_version()
        self.assertEqual('success', response['status'])

    def test_create_case_should_add_a_new_case(self):
        response = self._subject.get_cases()
        initial_case_count = len(response['data'])
        self._subject.create_case()
        response = self._subject.get_cases()
        case_count = len(response['data'])
        self.assertEqual(initial_case_count + 1, case_count)

    def test_update_case_should_not_require_case_name_issue_358(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        response = self._subject.update_case(case_identifier, {'case_tags': 'test,example'})
        self.assertEqual('success', response['status'])

    def test_graphql_endpoint_should_reject_requests_with_wrong_authentication_token(self):
        graphql_api = GraphQLApi(API_URL + '/graphql', 64*'0')
        payload = {
            'query': '{ cases { name } }'
        }
        response = graphql_api.execute(payload)
        self.assertEqual(401, response.status_code)

    def test_graphql_cases_should_contain_the_initial_case(self):
        payload = {
            'query': '{ cases { name } }'
        }
        body = self._subject.execute_graphql_query(payload)
        case_names = []
        for case in body['data']['cases']:
            case_names.append(case['name'])
        self.assertIn('#1 - Initial Demo', case_names)

    def _get_first_case(self, body):
        for case in body['data']['cases']:
            if case['name'] == '#1 - Initial Demo':
                return case

    def test_graphql_cases_should_have_a_global_identifier(self):
        payload = {
            'query': '{ cases { id name } }'
        }
        body = self._subject.execute_graphql_query(payload)
        first_case = self._get_first_case(body)
        self.assertEqual(b64encode(b'CaseObject:1').decode(), first_case['id'])

    def test_graphql_create_ioc_should_not_fail(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier} typeId: 1 tlpId: 1 value: "8.8.8.8") {{
                                           ioc {{ iocValue }}
                             }}
                         }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertNotIn('errors', body)

    def test_graphql_create_ioc_should_allow_optional_description_to_be_set(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        description = 'some description'
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier} typeId: 1 tlpId: 1 value: "8.8.8.8"
                                       description: "{description}") {{
                                           ioc {{ iocDescription }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(description, response['data']['iocCreate']['ioc']['iocDescription'])
