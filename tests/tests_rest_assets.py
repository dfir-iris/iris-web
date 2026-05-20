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
_CASE_ACCESS_LEVEL_READ_ONLY = 2
_CASE_ACCESS_LEVEL_FULL_ACCESS = 4


class TestsRestAssets(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_create_asset_should_return_201(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body)
        self.assertEqual(201, response.status_code)

    def test_create_asset_should_let_specify_analysis_status_id(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test', 'analysis_status_id': 3}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        self.assertEqual(3, response['analysis_status_id'])

    def test_get_asset_with_missing_asset_identifier_should_return_404(self):
        response = self._subject.get(f'/api/v2/asset/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_create_asset_with_missing_case_identifier_should_return_404(self):
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/assets', body)
        self.assertEqual(404, response.status_code)

    def test_create_asset_in_old_api_with_same_type_and_name_should_return_400(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        self._subject.create('/case/assets/add', body, {'cid': case_identifier})
        response = self._subject.create('/case/assets/add', body, {'cid': case_identifier})
        self.assertEqual(400, response.status_code)

    def test_create_asset_with_same_type_and_name_should_return_400(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body)
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body)
        self.assertEqual(400, response.status_code)

    def test_create_asset_with_asset_compromise_status_id_should_not_fail(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test', 'asset_compromise_status_id': 1}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        self.assertEqual(1, response['asset_compromise_status_id'])

    def test_create_asset_should_update_modification_history(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        modification = self._subject.get_most_recent_object_history_entry(response)
        self.assertEqual('created', modification['action'])

    def test_get_asset_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/assets/{asset_identifier}')
        self.assertEqual(200, response.status_code)

    def test_get_asset_should_return_404_after_it_was_deleted(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']
        self._subject.delete(f'/api/v2/cases/{case_identifier}/assets/{asset_identifier}')
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/assets/{asset_identifier}')
        self.assertEqual(404, response.status_code)

    def test_update_asset_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        identifier = response['asset_id']
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/assets/{identifier}',
                                        {'asset_type_id': 1, 'asset_name': 'new_asset_name'})
        self.assertEqual(200, response.status_code)

    def test_update_asset_should_return_correct_asset_uuid(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        identifier = response['asset_id']
        asset_uuid = response['asset_uuid']
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/assets/{identifier}',
                                        {'asset_type_id': 1, 'asset_name': 'new_asset_name'}).json()
        self.assertEqual(asset_uuid, response['asset_uuid'])

    def test_update_asset_should_return_404_when_asset_not_found(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/assets/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}',
                                        {'asset_type_id': 1, 'asset_name': 'new_asset_name'})
        self.assertEqual(404, response.status_code)

    def test_update_asset_should_allow_to_update_analysis_status(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        identifier = response['asset_id']
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/assets/{identifier}',
                                        {'asset_type_id': 1, 'asset_name': 'admin_laptop_test', 'analysis_status_id': 2}).json()
        self.assertEqual(2, response['analysis_status_id'])

    def test_update_asset_should_allow_to_update_asset_compromise_status_id(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test', 'asset_compromise_status_id': 1}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        identifier = response['asset_id']
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/assets/{identifier}',
                                        {'asset_type_id': 1, 'asset_name': 'admin_laptop_test', 'asset_compromise_status_id': 2}).json()
        self.assertEqual(2, response['asset_compromise_status_id'])

    def test_update_asset_should_update_modification_history(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        identifier = response['asset_id']
        body = {'asset_type_id': 1, 'asset_name': 'new_asset_name'}
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/assets/{identifier}', body).json()
        modification = self._subject.get_most_recent_object_history_entry(response)
        self.assertEqual('updated', modification['action'])

    def test_delete_asset_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}/assets/{asset_identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_asset_with_missing_asset_identifier_should_return_404(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}/assets/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_delete_asset_should_increment_asset_state(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']
        response = self._subject.get('/case/assets/state', {'cid': case_identifier}).json()
        state = response['data']['object_state']
        self._subject.delete(f'/api/v2/cases/{case_identifier}/assets/{asset_identifier}')
        response = self._subject.get('/case/assets/state', {'cid': case_identifier}).json()
        self.assertEqual(state + 1, response['data']['object_state'])

    def test_delete_asset_should_not_fail_when_it_is_linked_to_an_ioc(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        ioc_identifier = response['ioc_id']
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test', 'ioc_links': [ioc_identifier]}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}/assets/{asset_identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_asset_should_not_fail_when_it_has_associated_comments(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']
        self._subject.create(f'/case/assets/{asset_identifier}/comments/add', {'comment_text': 'comment text'})
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}/assets/{asset_identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_asset_should_delete_associated_comments(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']
        response = self._subject.create(f'/case/assets/{asset_identifier}/comments/add', {'comment_text': 'comment text'}).json()
        comment_identifier = response['data']['comment_id']
        self._subject.delete(f'/api/v2/cases/{case_identifier}/assets/{asset_identifier}')
        response = self._subject.create(f'/case/assets/{case_identifier}/comments/{comment_identifier}/edit', {'comment_text': 'new comment text'})
        # TODO should ideally rather be 404 here
        self.assertEqual(400, response.status_code)

    def test_user_should_not_change_comment_of_others(self):
        user1 = self._subject.create_dummy_user()
        user2 = self._subject.create_dummy_user()

        # Create a case
        case_identifier = self._subject.create_dummy_case()

        # Give access to users
        body = {
            'cases_list': [case_identifier],
            'access_level': _CASE_ACCESS_LEVEL_FULL_ACCESS
        }
        self._subject.create(f'/manage/users/{user2.get_identifier()}/cases-access/update', body)
        self._subject.create(f'/manage/users/{user1.get_identifier()}/cases-access/update', body)

        # Create a new asset
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = user1.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        asset_identifier = response['asset_id']

        # Create a comment in the new asset
        response = user1.create(f'/case/assets/{asset_identifier}/comments/add?cid={case_identifier}', {'comment_text': 'comment text'}).json()
        comment_identifier = response['data']['comment_id']

        # Try to update the comment from user 2
        response = user2.create(f'/case/assets/{asset_identifier}/comments/{comment_identifier}/edit?cid={case_identifier}', {'comment_text': 'updated comment'})
        self.assertEqual(400, response.status_code)

    def test_get_assets_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/assets')
        self.assertEqual(200, response.status_code)

    def test_get_assets_should_return_404_when_case_does_not_exist(self):
        response = self._subject.get(f'/api/v2/cases/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/assets')
        self.assertEqual(404, response.status_code)

    def test_get_assets_should_return_current_page(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/assets').json()
        self.assertEqual(1, response['current_page'])

    def test_get_assets_should_return_existing_assets(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'asset'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/assets').json()
        self.assertEqual(1, len(response['data']))

    def test_get_assets_should_accept_per_page_query_parameter(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'asset1'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        body = {'asset_type_id': 1, 'asset_name': 'asset2'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/assets', {'per_page': 1}).json()
        self.assertEqual(1, len(response['data']))

    def test_get_assets_should_accept_order_by_query_parameter(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'asset2'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        body = {'asset_type_id': 1, 'asset_name': 'asset1'}
        self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/assets', {'order_by': 'asset_name'}).json()
        self.assertEqual('asset1', response['data'][0]['asset_name'])

    def test_get_assets_should_return_200_when_user_has_read_only_access_to_case(self):
        case_identifier = self._subject.create_dummy_case()

        user = self._subject.create_dummy_user()
        body = {
            'cases_list': [case_identifier],
            'access_level': _CASE_ACCESS_LEVEL_READ_ONLY
        }
        self._subject.create(f'/manage/users/{user.get_identifier()}/cases-access/update', body)
        response = user.get(f'/api/v2/cases/{case_identifier}/assets')
        self.assertEqual(200, response.status_code)

    def test_upload_asset_csv_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()

        body = {
            'CSVData': 'asset_name,asset_type_name,asset_description,asset_ip,asset_domain,asset_tags\n    "My computer","Mac - Computer","Computer of Mme Michu","192.168.15.5","iris.local","Compta|Mac"'
        }
        response = self._subject.create('/case/assets/upload', body, query_parameters={'cid': case_identifier})
        self.assertEqual(200, response.status_code)
