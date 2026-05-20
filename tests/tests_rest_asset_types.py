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

_FIRST_ASSET_TYPE_IDENTIFIER = 1


class TestsRestAssetTypes(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_update_asset_type_should_return_200(self):
        url = f'/manage/asset-type/update/{_FIRST_ASSET_TYPE_IDENTIFIER}'
        data = {'asset_name': 'Account', 'asset_description': 'Generic Account'}
        with open('data/img/desktop.png', 'rb') as file_not_compromised:
            files = {'asset_icon_not_compromised': file_not_compromised, 'asset_icon_compromised': ('', '')}
            response = self._subject.post_multipart_encoded_files(url, data, files)
            self.assertEqual(200, response.status_code)
