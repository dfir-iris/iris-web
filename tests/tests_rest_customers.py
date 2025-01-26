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

_PERMISSION_CUSTOMERS_WRITE = 0x80
_IRIS_INITIAL_CLIENT_IDENTIFIER = 1


class TestsRestCustomers(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()
        users = self._subject.get('/manage/users/list').json()
        for user in users['data']:
            identifier = user['user_id']
            body = {'customers_membership': [_IRIS_INITIAL_CLIENT_IDENTIFIER]}
            self._subject.create(f'/manage/users/{identifier}/customers/update', body)
        customers = self._subject.get('/manage/customers/list').json()
        for customer in customers['data']:
            identifier = customer['customer_id']
            self._subject.create(f'/manage/customers/delete/{identifier}', {})

    def test_create_customer_should_return_200_when_user_has_customer_write_right(self):
        body = {
            'group_name': 'Customer create',
            'group_description': 'Group with customers_write right',
            'group_permissions': [_PERMISSION_CUSTOMERS_WRITE]
        }
        response = self._subject.create('/manage/groups/add', body).json()
        group_identifier = response['data']['group_id']
        user = self._subject.create_dummy_user()
        body = {'groups_membership': [group_identifier]}
        self._subject.create(f'/manage/users/{user.get_identifier()}/groups/update', body)

        body = {'custom_attributes': {}, 'customer_description': '', 'customer_name': 'Customer', 'customer_sla': ''}
        response = user.create('/manage/customers/add', body)

        self.assertEqual(200, response.status_code)
