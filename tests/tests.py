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
import requests
from iris import _API_KEY, _API_URL


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
        response = self._subject.create_case()
        case_identifier = response['data']['case_id']
        response = self._subject.update_case(case_identifier, {'case_tags': 'test,example'})
        self.assertEqual('success', response['status'])

    # TODO rewrite this test in a nicer way (too low level)
    # TODO use gql
    def test_graphql_endpoint_should_not_fail(self):
        url = _API_URL + '/graphql'
        _headers = {'Authorization': f'Bearer {_API_KEY}', 'Content-Type': 'application/json'}
        payload = {
            'query': '{ hello(firstName: "Paul") }'
        }
        response = requests.post(_API_URL + '/graphql', headers=_headers, json=payload)
        body = response.json()
        self.assertEqual('Hello Paul!', body['data']['hello'])

    # TODO rewrite this test in a nicer way (too low level)
    def test_graphql_endpoint_should_reject_requests_with_wrong_authentication_token(self):
        url = _API_URL + '/graphql'
        _headers = {'Authorization': f'Bearer 0000000000000000000000000000000000000000000000000000000000000000', 'Content-Type': 'application/json'}
        payload = {
            'query': '{ hello(firstName: "friendly") }'
        }
        response = requests.post(url, headers=_headers, json=payload)
        self.assertEqual(401, response.status_code)
