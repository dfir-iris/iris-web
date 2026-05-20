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
from iris import IRIS_PERMISSION_CUSTOMERS_WRITE
from iris import ADMINISTRATOR_USER_IDENTIFIER
from iris import IRIS_INITIAL_CUSTOMER_IDENTIFIER

_IDENTIFIER_FOR_NONEXISTENT_OBJECT = 123456789


class TestsRestCustomers(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_create_customer_should_return_200_when_user_has_customer_write_right(self):
        group_identifier = self._subject.create_dummy_group([IRIS_PERMISSION_CUSTOMERS_WRITE])
        user = self._subject.create_dummy_user()
        body = {'groups_membership': [group_identifier]}
        self._subject.create(f'/manage/users/{user.get_identifier()}/groups/update', body)

        body = {'custom_attributes': {}, 'customer_description': '', 'customer_name': 'Customer', 'customer_sla': ''}
        response = user.create('/manage/customers/add', body)

        self.assertEqual(200, response.status_code)

    def test_create_customer_should_return_201(self):
        body = {'customer_name': 'customer'}
        response = self._subject.create('/api/v2/manage/customers', body)
        self.assertEqual(201, response.status_code)

    def test_create_customer_should_return_customer_name(self):
        body = {'customer_name': 'customer'}
        response = self._subject.create('/api/v2/manage/customers', body).json()
        self.assertEqual('customer', response['customer_name'])

    def test_create_customer_should_return_400_when_another_customer_with_the_same_name_already_exists(self):
        body = {'customer_name': 'customer'}
        self._subject.create('/api/v2/manage/customers', body)
        response = self._subject.create('/api/v2/manage/customers', body)
        self.assertEqual(400, response.status_code)

    def test_create_customer_should_return_400_when_field_customer_name_is_not_provided(self):
        response = self._subject.create('/api/v2/manage/customers', {})
        self.assertEqual(400, response.status_code)

    def test_create_customer_should_add_an_activity(self):
        body = {'customer_name': 'customer_name'}
        self._subject.create('/api/v2/manage/customers', body)
        last_activity = self._subject.get_latest_activity()
        self.assertEqual('Added customer customer_name', last_activity['activity_desc'])

    def test_create_customer_should_add_user_to_the_customer(self):
        body = {'customer_name': 'customer_name'}
        response = self._subject.create('/api/v2/manage/customers', body).json()
        identifier = response['customer_id']
        response = self._subject.get(f'/api/v2/manage/users/{ADMINISTRATOR_USER_IDENTIFIER}').json()
        user_customers_identifiers = []
        for customer in response['user_customers']:
            user_customers_identifiers.append(customer['customer_id'])
        self.assertIn(identifier, user_customers_identifiers)

    def test_get_customer_should_return_200(self):
        body = {'customer_name': 'customer'}
        response = self._subject.create('/api/v2/manage/customers', body).json()
        identifier = response['customer_id']
        response = self._subject.get(f'/api/v2/manage/customers/{identifier}')
        self.assertEqual(200, response.status_code)

    def test_get_customer_should_return_404_when_customer_does_not_exist(self):
        response = self._subject.get(f'/api/v2/manage/customers/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_get_customer_should_return_403_when_user_has_no_permission_to_read_customers(self):
        body = {'customer_name': 'customer'}
        response = self._subject.create('/api/v2/manage/customers', body).json()
        identifier = response['customer_id']

        user = self._subject.create_dummy_user()
        response = user.get(f'/api/v2/manage/customers/{identifier}')
        self.assertEqual(403, response.status_code)

    def test_put_customer_should_return_200(self):
        body = {'customer_name': 'customer'}
        response = self._subject.create('/api/v2/manage/customers', body).json()
        identifier = response['customer_id']

        body = {'customer_name': 'new name'}
        response = self._subject.update(f'/api/v2/manage/customers/{identifier}', body)
        self.assertEqual(200, response.status_code)

    def test_put_customer_should_return_400_when_another_customer_with_the_same_name_already_exists(self):
        body = {'customer_name': 'already existing name'}
        self._subject.create('/api/v2/manage/customers', body).json()

        body = {'customer_name': 'customer'}
        response = self._subject.create('/api/v2/manage/customers', body).json()
        identifier = response['customer_id']

        body = {'customer_name': 'already existing name'}
        response = self._subject.update(f'/api/v2/manage/customers/{identifier}', body)
        self.assertEqual(400, response.status_code)

    def test_put_customer_should_return_200_when_updating_with_same_name(self):
        body = {'customer_name': 'customer'}
        response = self._subject.create('/api/v2/manage/customers', body).json()
        identifier = response['customer_id']

        body = {'customer_name': 'customer'}
        response = self._subject.update(f'/api/v2/manage/customers/{identifier}', body)
        self.assertEqual(200, response.status_code)

    def test_delete_customer_should_return_204(self):
        body = {'customer_name': 'customer'}
        response = self._subject.create('/api/v2/manage/customers', body).json()
        identifier = response['customer_id']

        # TODO currently, to remove a customer, no user should have any access to it. I am not sure this is the optimum behavior.
        body = {'customers_membership': [IRIS_INITIAL_CUSTOMER_IDENTIFIER]}
        self._subject.create(f'/manage/users/{ADMINISTRATOR_USER_IDENTIFIER}/customers/update', body)

        response = self._subject.delete(f'/api/v2/manage/customers/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_customer_should_return_400_when_referenced_in_a_case(self):
        body = {'customer_name': 'customer'}
        response = self._subject.create('/api/v2/manage/customers', body).json()
        identifier = response['customer_id']

        self._subject.create_dummy_case(identifier)

        # TODO currently, to remove a customer, no user should have any access to it. I am not sure this is the optimum behavior.
        body = {'customers_membership': [IRIS_INITIAL_CUSTOMER_IDENTIFIER]}
        self._subject.create(f'/manage/users/{ADMINISTRATOR_USER_IDENTIFIER}/customers/update', body)

        response = self._subject.delete(f'/api/v2/manage/customers/{identifier}')
        self.assertEqual(400, response.status_code)

    def test_search_customers_should_return_200(self):
        response = self._subject.get('/api/v2/manage/customers')
        self.assertEqual(200, response.status_code)
