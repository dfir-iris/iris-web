#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
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
from iris import IRIS_PERMISSION_SERVER_ADMINISTRATOR
from iris import ADMINISTRATOR_USER_IDENTIFIER
from iris import GROUP_ANALYSTS_IDENTIFIER

_IDENTIFIER_FOR_NONEXISTENT_OBJECT = 123456789


class TestsRestGroups(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_create_group_should_return_201(self):
        body = {'group_name': 'name', 'group_description': 'description'}
        response = self._subject.create('/api/v2/manage/groups', body)
        self.assertEqual(201, response.status_code)

    def test_create_group_should_set_group_name(self):
        body = {'group_name': 'name', 'group_description': 'description'}
        response = self._subject.create('/api/v2/manage/groups', body).json()
        self.assertEqual('name', response['group_name'])

    def test_create_group_should_return_valid_group_uuid(self):
        body = {'group_name': 'name', 'group_description': 'description'}
        response = self._subject.create('/api/v2/manage/groups', body).json()
        self.assertIsNotNone(response['group_uuid'])

    def test_create_group_should_return_400_when_field_group_description_is_missing(self):
        body = {'group_name': 'name'}
        response = self._subject.create('/api/v2/manage/groups', body)
        self.assertEqual(400, response.status_code)

    def test_create_group_should_return_400_when_field_group_description_is_not_a_string(self):
        body = {'group_name': 'name', 'group_description': 1}
        response = self._subject.create('/api/v2/manage/groups', body)
        self.assertEqual(400, response.status_code)

    def test_create_group_should_return_400_when_a_group_with_the_same_name_already_exists(self):
        body = {'group_name': 'name', 'group_description': 'description'}
        self._subject.create('/api/v2/manage/groups', body)
        response = self._subject.create('/api/v2/manage/groups', body)
        self.assertEqual(400, response.status_code)

    def test_create_group_should_return_403_when_user_has_insufficient_permissions(self):
        user = self._subject.create_dummy_user()
        body = {'group_name': 'name', 'group_description': 'description'}
        response = user.create('/api/v2/manage/groups', body)
        self.assertEqual(403, response.status_code)

    def test_get_group_should_return_200(self):
        body = {'group_name': 'name', 'group_description': 'description'}
        response = self._subject.create('/api/v2/manage/groups', body).json()
        identifier = response['group_id']
        response = self._subject.get(f'/api/v2/manage/groups/{identifier}')
        self.assertEqual(200, response.status_code)

    def test_get_group_analysts_should_return_field_autofollow_to_false(self):
        group_analysts = self._subject.get(f'/api/v2/manage/groups/{GROUP_ANALYSTS_IDENTIFIER}').json()
        self.assertFalse(group_analysts['group_auto_follow'])

    def test_get_group_should_return_group_name(self):
        body = {'group_name': 'name', 'group_description': 'description'}
        response = self._subject.create('/api/v2/manage/groups', body).json()
        identifier = response['group_id']
        response = self._subject.get(f'/api/v2/manage/groups/{identifier}').json()
        self.assertEqual('name', response['group_name'])

    def test_get_group_should_return_404_when_group_does_not_exist(self):
        response = self._subject.get(f'/api/v2/manage/groups/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_get_group_should_return_403_when_user_has_insufficient_permissions(self):
        body = {'group_name': 'name', 'group_description': 'description'}
        response = self._subject.create('/api/v2/manage/groups', body).json()
        identifier = response['group_id']

        user = self._subject.create_dummy_user()
        response = user.get(f'/api/v2/manage/groups/{identifier}')
        self.assertEqual(403, response.status_code)

    def test_update_group_should_return_200(self):
        body = {'group_name': 'name', 'group_description': 'description'}
        response = self._subject.create('/api/v2/manage/groups', body).json()
        identifier = response['group_id']
        body = {'group_name': 'new_name', 'group_description': 'new_description', 'group_permissions': 1}
        response = self._subject.update(f'/api/v2/manage/groups/{identifier}', body)
        self.assertEqual(200, response.status_code)

    def test_update_group_should_return_field_group_name(self):
        new_name = 'new_name'
        body = {'group_name': 'name', 'group_description': 'description'}
        response = self._subject.create('/api/v2/manage/groups', body).json()
        identifier = response['group_id']
        body = {'group_name': new_name, 'group_description': 'new_description', 'group_permissions': 1}
        response = self._subject.update(f'/api/v2/manage/groups/{identifier}', body).json()
        self.assertEqual(new_name, response['group_name'])

    def test_update_group_should_return_field_group_auto_follow(self):
        body = {'group_name': 'name', 'group_description': 'description'}
        response = self._subject.create('/api/v2/manage/groups', body).json()
        identifier = response['group_id']
        body = {'group_name': 'new_name', 'group_description': 'new_description', 'group_permissions': 1, 'group_auto_follow': True}
        response = self._subject.update(f'/api/v2/manage/groups/{identifier}', body).json()
        self.assertEqual(True, response['group_auto_follow'])

    def test_update_group_should_return_400_when_field_group_name_is_missing(self):
        body = {'group_name': 'name', 'group_description': 'description'}
        response = self._subject.create('/api/v2/manage/groups', body).json()
        identifier = response['group_id']
        body = {'group_description': 'new_description', 'group_permissions': 1}
        response = self._subject.update(f'/api/v2/manage/groups/{identifier}', body)
        self.assertEqual(400, response.status_code)

    def test_update_group_should_return_403_when_user_has_no_permission_to_update_group(self):
        user = self._subject.create_dummy_user()
        body = {'group_name': 'name', 'group_description': 'description'}
        response = self._subject.create('/api/v2/manage/groups', body).json()
        identifier = response['group_id']
        body = {'group_description': 'new_description', 'group_permissions': 1}
        response = user.update(f'/api/v2/manage/groups/{identifier}', body)
        self.assertEqual(403, response.status_code)

    def test_update_group_should_return_404_when_group_not_found(self):
        body = {'group_name': 'name', 'group_description': 'description', 'group_permissions': 1}
        response = self._subject.update(f'/api/v2/manage/groups/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}', body)
        self.assertEqual(404, response.status_code)

    def test_update_group_should_return_400_when_new_user_in_group_with_permissions_admin(self):
        group_identifier = self._subject.create_dummy_group([IRIS_PERMISSION_SERVER_ADMINISTRATOR])
        user = self._subject.create_dummy_user()
        body = {'groups_membership': [group_identifier]}
        self._subject.create(f'/manage/users/{user.get_identifier()}/groups/update', body)
        body = {'group_name': 'new_name', 'group_description': 'new_description', 'group_permissions': 0x0}
        response = user.update(f'/api/v2/manage/groups/{group_identifier}', body)
        self.assertEqual(400, response.status_code)

    def test_delete_group_should_return_204(self):
        body = {'group_name': 'name', 'group_description': 'description'}
        response = self._subject.create('/api/v2/manage/groups', body).json()
        identifier = response['group_id']
        response = self._subject.delete(f'/api/v2/manage/groups/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_get_group_should_return_404_after_delete_group(self):
        body = {'group_name': 'name', 'group_description': 'description'}
        response = self._subject.create('/api/v2/manage/groups', body).json()
        identifier = response['group_id']
        self._subject.delete(f'/api/v2/manage/groups/{identifier}')
        response = self._subject.get(f'/api/v2/manage/groups/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_delete_group_should_return_404_when_group_not_found(self):
        response = self._subject.delete(f'/api/v2/manage/groups/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_delete_group_should_return_403_when_user_is_denied_permission_to_access_group(self):
        user = self._subject.create_dummy_user()
        body = {'group_name': 'name', 'group_description': 'description'}
        response = self._subject.create('/api/v2/manage/groups', body).json()
        identifier = response['group_id']
        response = user.delete(f'/api/v2/manage/groups/{identifier}')
        self.assertEqual(403, response.status_code)

    def test_delete_group_should_return_400_when_user_would_lose_server_administrator_permission(self):
        response = self._subject.get(f'/api/v2/manage/users/{ADMINISTRATOR_USER_IDENTIFIER}').json()
        user_groups = response['user_groups']
        administrator_group_identifier = user_groups[0]['group_id']
        response = self._subject.delete(f'/api/v2/manage/groups/{administrator_group_identifier}')
        self.assertEqual(400, response.status_code)
