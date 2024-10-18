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


class TestsRestAssets(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_delete_asset_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': '1', 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']
        response = self._subject.delete(f'/api/v2/assets/{asset_identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_asset_with_missing_asset_identifier_should_return_404(self):
        response = self._subject.delete(f'/api/v2/assets/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_create_asset_should_work(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': '1', 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body)
        self.assertEqual(201, response.status_code)

    def test_get_asset_with_missing_asset_identifier_should_return_404(self):
        response = self._subject.get(f'/api/v2/asset/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_create_asset_with_missing_case_identifier_should_return_404(self):
        body = {'asset_type_id': '1', 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/assets', body)
        self.assertEqual(404, response.status_code)

    def test_create_asset_in_old_api_with_same_type_and_name_should_return_400(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': '1', 'asset_name': 'admin_laptop_test'}
        self._subject.create('/case/assets/add', body, {'cid': case_identifier})
        response = self._subject.create('/case/assets/add', body, {'cid': case_identifier})
        self.assertEqual(400, response.status_code)

    def test_create_asset_with_same_type_and_name_should_return_400(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': '1', 'asset_name': 'admin_laptop_test'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body)
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body)
        self.assertEqual(400, response.status_code)

    def test_get_asset_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': '1', 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']
        response = self._subject.get(f'/api/v2/assets/{asset_identifier}')
        self.assertEqual(200, response.status_code)

    def test_get_asset_should_return_404_when_it_was_deleted(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': '1', 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']
        self._subject.delete(f'/api/v2/assets/{asset_identifier}')
        response = self._subject.get(f'/api/v2/assets/{asset_identifier}')
        self.assertEqual(404, response.status_code)

    def test_delete_asset_should_increment_asset_state(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': '1', 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']
        response = self._subject.get('/case/assets/state', {'cid': case_identifier}).json()
        state = response['data']['object_state']
        self._subject.delete(f'/api/v2/assets/{asset_identifier}')
        response = self._subject.get('/case/assets/state', {'cid': case_identifier}).json()
        self.assertEqual(state + 1, response['data']['object_state'])

    def test_delele_asset_should_not_fail_when_it_is_linked_to_an_ioc(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        ioc_identifier = response['ioc_id']
        body = {'asset_type_id': '1', 'asset_name': 'admin_laptop_test', 'ioc_links': [ioc_identifier]}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']
        response = self._subject.delete(f'/api/v2/assets/{asset_identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_asset_should_not_fail_when_it_has_associated_comments(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': '1', 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']
        self._subject.create(f'/case/assets/{asset_identifier}/comments/add', {'comment_text': 'comment text'})
        response = self._subject.delete(f'/api/v2/assets/{asset_identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_asset_should_delete_associated_comments(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': '1', 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']
        response = self._subject.create(f'/case/assets/{asset_identifier}/comments/add', {'comment_text': 'comment text'}).json()
        comment_identifier = response['data']['comment_id']
        self._subject.delete(f'/api/v2/assets/{asset_identifier}')
        response = self._subject.create(f'/case/assets/{case_identifier}/comments/{comment_identifier}/edit', {'comment_text': 'new comment text'})
        # TODO should ideally rather be 404 here
        self.assertEqual(400, response.status_code)
