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

# TODO should change None into 123456789 and maybe fix...
_IDENTIFIER_FOR_NONEXISTENT_OBJECT = None


class TestsRestAssets(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

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
