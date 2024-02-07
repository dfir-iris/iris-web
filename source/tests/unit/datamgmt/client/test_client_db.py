#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
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

from app.datamgmt.client.client_db import get_client, get_client_list, update_client, delete_client
from app.datamgmt.exceptions.ElementExceptions import ElementNotFoundException
from tests.clean_database import clean_db
from tests.test_helper import TestHelper


class TestClientDB(TestCase):
    def setUp(self) -> None:
        self._test_helper = TestHelper()
        clean_db()

    def tearDown(self) -> None:
        clean_db()

    # CREATE CLIENT
    def test_create_client_should_return_client_object(self):
        new_client = self._test_helper.create_client("new_client_name")

        self.assertIsNotNone(new_client)
        self.assertEqual("new_client_name", new_client.name)

    # GET CLIENT
    def test_get_client_should_return_client_object(self):
        # Create 2 clients
        client1 = self._test_helper.create_client()
        self._test_helper.create_client()

        # Get client1
        returned_client = get_client(client1.client_id)

        self.assertIsNotNone(returned_client)
        self.assertEqual(returned_client.client_id, client1.client_id)

    # GET CLIENT LIST
    def test_get_client_list_should_return_list_of_client_object(self):
        # Create 3 clients
        client1 = self._test_helper.create_client()
        client2 = self._test_helper.create_client()
        client3 = self._test_helper.create_client()

        # Get client list
        returned_client_list = get_client_list()

        self.assertEqual(3, len(returned_client_list))
        returned_client_id_list = [el['client_id'] for el in returned_client_list]
        self.assertTrue(client1.client_id in returned_client_id_list)
        self.assertTrue(client2.client_id in returned_client_id_list)
        self.assertTrue(client3.client_id in returned_client_id_list)

    def test_get_client_list_should_return_list_of_client_object_for_api(self):
        # Create 3 clients
        client1 = self._test_helper.create_client()
        client2 = self._test_helper.create_client()
        client3 = self._test_helper.create_client()

        # Get client list
        returned_client_list = get_client_list(True)

        self.assertEqual(3, len(returned_client_list))
        returned_client_id_list = [client_id for _, client_id in returned_client_list]
        self.assertTrue(client1.client_id in returned_client_id_list)
        self.assertTrue(client2.client_id in returned_client_id_list)
        self.assertTrue(client3.client_id in returned_client_id_list)

    # UPDATE CLIENT
    def test_update_client_should_correctly_modify_client(self):
        client1 = self._test_helper.create_client()

        new_name = 'updated name'
        update_client(client1.client_id, new_name)

        returned_client = get_client(client1.client_id)

        self.assertEqual(returned_client.name, new_name)

    def test_update_client_should_raise_error_if_client_id_not_found(self):
        with self.assertRaises(ElementNotFoundException):
            update_client(0, 'new_name')

    # DELETE CLIENT
    def test_delete_client_should_correctly_remove_client(self):
        client1 = self._test_helper.create_client()
        client2 = self._test_helper.create_client()

        delete_client(client1.client_id)

        client_list = get_client_list()

        self.assertEqual(1, len(client_list))
        self.assertEqual(client2.client_id, client_list[0]['client_id'])

    def test_delete_client_should_raise_error_if_client_id_not_found(self):
        with self.assertRaises(ElementNotFoundException):
            delete_client(0)
