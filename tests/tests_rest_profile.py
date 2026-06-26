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


class TestsRestProfile(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_get_me_should_return_200(self):
        response = self._subject.get('/api/v2/me')
        self.assertEqual(200, response.status_code)

    def test_update_me_should_return_200(self):
        response = self._subject.update('/api/v2/me', {})
        self.assertEqual(200, response.status_code)

    def test_update_me_should_modify_user_name(self):
        user = self._subject.create_user('name', 'aA.1234567890')

        response = user.update('/api/v2/me', {'user_name': 'new name'}).json()
        self.assertEqual('new name', response['user_name'])

    def test_update_me_should_modify_user_email(self):
        user = self._subject.create_dummy_user()

        response = user.update('/api/v2/me', {'user_email': 'new@aa.eu'}).json()
        self.assertEqual('new@aa.eu', response['user_email'])

    def test_update_me_should_modify_user_password(self):
        user = self._subject.create_user('name', 'aA.1234567890')
        user.update('/api/v2/me', {
            'user_current_password': 'aA.1234567890',
            'user_password': 'bB.1234567890'
        })
        response = user.login('bB.1234567890')
        self.assertEqual(200, response.status_code)

    def test_update_me_should_return_400_when_changing_password_without_current_password(self):
        user = self._subject.create_user('pwdrequired', 'aA.1234567890')
        response = user.update('/api/v2/me', {'user_password': 'bB.1234567890'})
        self.assertEqual(400, response.status_code)

    def test_update_me_should_return_400_when_changing_password_with_wrong_current_password(self):
        user = self._subject.create_user('pwdwrong', 'aA.1234567890')
        response = user.update('/api/v2/me', {
            'user_current_password': 'wrong-password',
            'user_password': 'bB.1234567890'
        })
        self.assertEqual(400, response.status_code)

    def test_update_me_should_not_change_password_when_current_password_is_wrong(self):
        user = self._subject.create_user('pwdkeep', 'aA.1234567890')
        user.update('/api/v2/me', {
            'user_current_password': 'wrong-password',
            'user_password': 'bB.1234567890'
        })
        response = user.login('aA.1234567890')
        self.assertEqual(200, response.status_code)

    def test_update_me_should_modify_ctx_case(self):
        user = self._subject.create_dummy_user()
        case_identifier = self._subject.create_dummy_case()
        response = user.update('/api/v2/me', {'ctx_case': case_identifier}).json()
        self.assertEqual(case_identifier, response['ctx_case'])

    def test_update_me_should_modify_in_dark_mode(self):
        user = self._subject.create_dummy_user()

        response = user.update('/api/v2/me', {'in_dark_mode': True}).json()
        self.assertTrue(response['in_dark_mode'])

    def test_update_me_should_modify_has_deletion_confirmation(self):
        user = self._subject.create_dummy_user()

        response = user.update('/api/v2/me', {'has_deletion_confirmation': True}).json()
        self.assertTrue(response['has_deletion_confirmation'])

    def test_update_me_should_modify_has_mini_sidebar(self):
        user = self._subject.create_dummy_user()

        response = user.update('/api/v2/me', {'has_mini_sidebar': True}).json()
        self.assertTrue(response['has_mini_sidebar'])

    def test_update_me_should_not_be_able_to_modify_user_active(self):
        user = self._subject.create_dummy_user()

        response = user.update('/api/v2/me', {'user_active': False}).json()
        self.assertTrue(response['user_active'])

    def test_update_me_should_not_be_able_to_modify_user_is_service_account(self):
        user = self._subject.create_dummy_user()

        response = user.update('/api/v2/me', {'user_is_service_account': True}).json()
        self.assertFalse(response['user_is_service_account'])

    def test_update_me_should_not_be_able_to_modify_user_id(self):
        user = self._subject.create_dummy_user()
        identifier = user.get_identifier()

        response = user.update('/api/v2/me', {'user_id': 0}).json()
        self.assertEqual(identifier, response['user_id'])

    def test_update_me_should_not_be_able_to_modify_uuid(self):
        user = self._subject.create_dummy_user()
        identifier = user.get_identifier()

        response = self._subject.get(f'/api/v2/manage/users/{identifier}').json()
        print(response['uuid'])

        uuid = response['uuid']
        response = user.update('/api/v2/me', {'uuid': '21f1afb7-0c56-4e5a-8359-71f73d481a8e'}).json()
        self.assertEqual(uuid, response['uuid'])

    def test_update_me_should_not_modify_user_primary_organisation_id(self):
        user = self._subject.create_dummy_user()
        identifier = user.get_identifier()

        response = self._subject.get(f'/api/v2/manage/users/{identifier}').json()
        primary_organisation_identifier = response['user_primary_organisation_id']
        response = user.update('/api/v2/me', {'user_primary_organisation_id': 0}).json()
        self.assertEqual(primary_organisation_identifier, response['user_primary_organisation_id'])

    def test_update_me_should_return_400_when_field_user_name_is_not_a_string(self):
        user = self._subject.create_dummy_user()

        response = user.update('/api/v2/me', {'user_name': 123})
        self.assertEqual(400, response.status_code)

    def test_renew_api_key_should_return_200(self):
        user = self._subject.create_dummy_user()
        response = user.create('/api/v2/me/api-key/renew', {})
        self.assertEqual(200, response.status_code)

    def test_renew_api_key_should_change_api_key(self):
        user = self._subject.create_dummy_user()
        before = user.get('/api/v2/me').json()['user_api_key']
        response = user.create('/api/v2/me/api-key/renew', {}).json()
        self.assertNotEqual(before, response['user_api_key'])

    def test_refresh_permissions_should_return_200(self):
        user = self._subject.create_dummy_user()
        response = user.create('/api/v2/me/permissions/refresh', {})
        self.assertEqual(200, response.status_code)

    def test_get_context_should_return_200(self):
        response = self._subject.get('/api/v2/me/context')
        self.assertEqual(200, response.status_code)

    def test_get_context_should_expose_iris_version(self):
        response = self._subject.get('/api/v2/me/context').json()
        self.assertIn('iris_version', response)
        self.assertIsInstance(response['iris_version'], str)
        self.assertTrue(response['iris_version'])

    def test_get_context_should_expose_demo_mode_flag(self):
        response = self._subject.get('/api/v2/me/context').json()
        self.assertIn('demo_mode', response)
        self.assertIsInstance(response['demo_mode'], bool)

    def test_get_context_should_expose_permission_mask_and_names(self):
        response = self._subject.get('/api/v2/me/context').json()
        permissions = response.get('permissions') or {}
        self.assertIn('mask', permissions)
        self.assertIn('names', permissions)
        self.assertIsInstance(permissions['mask'], int)
        self.assertIsInstance(permissions['names'], list)
        # Every authenticated user gets standard_user implicitly.
        self.assertIn('standard_user', permissions['names'])
