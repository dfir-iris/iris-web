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


from os import environ
from unittest import TestCase

import re
from flask import url_for
from flask.testing import FlaskClient
from random import randrange

from app import app
from app.datamgmt.client.client_db import create_client
from app.models import Client


class TestHelper(TestCase):
    @staticmethod
    def log_in(test_app: FlaskClient) -> None:
        login_page = test_app.get('/login')

        csrf_token = re.search(r'id="csrf_token" name="csrf_token" type="hidden" value="(.*?)"', str(login_page.data)).group(1)

        test_app.post('/login', data=dict(username='administrator', password=environ.get("IRIS_ADM_PASSWORD", ""), csrf_token=csrf_token), follow_redirects=True)

    def verify_path_without_cid_redirects_correctly(self, path: str, assert_string: str):
        with app.test_client() as test_app:
            self.log_in(test_app)

            result = test_app.get(url_for(path))

            self.assertEqual(302, result.status_code)
            self.assertIn(assert_string, str(result.data))

            result2 = test_app.get(url_for(path), follow_redirects=True)

            self.assertEqual(200, result2.status_code)

    @staticmethod
    def create_client(client_name: str = None) -> Client:
        client_name = client_name if client_name is not None else f"client_name_{randrange(1,10000)}"

        new_client = create_client(client_name)

        return new_client
