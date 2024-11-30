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
from typing import Literal, Optional
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

    # MARK: Flask helpers -----------------------------------------------------

    @staticmethod
    def get_flask_test_client() -> FlaskClient:
        return app.test_client()
    
    @staticmethod
    def perform_request(test: TestCase, blueprint_name: str, method: Literal["get", "post", "put", "patch", "delete"], /, data: Optional[dict] = None, json: Optional[dict] = None, expected_status: int | list[int] = [200, 204]):
        """Performs an API request, matching the expected status code, while returning the result. 
        
        Using the blueprint name, this method will automatically determine the endpoint url for you.

        Args:
            blueprint_name (str): the blueprint name (eg: rest_v2.case.create).
            method (Literal["get", "post", "put", "patch", "delete"]): the HTTP method.
            data (dict, optional): Any Form data to submit with the request. Defaults to None.
            json (dict, optional): Any JSON data to submit with the request. Defaults to None.
            expected_status (int | list[int], optional): The expected returned status code(s). Defaults to [200, 204].
        """
        
        # Get endpoint based on the blueprint name
        endpoint = url_for(blueprint_name)
        
        # Ensure `expected_status` is a list
        if not type(expected_status) == list:
            expected_status = [expected_status]
        
        # Create test client
        with app.test_client() as test_client:
            # Send req
            req = test_client.open(endpoint, method=method, data=data, json=json)
            
            # Assert the status code
            test.assertIn(req.status_code, expected_status)
            
            # Return json or text, if not valid JSON
            return req.get_json(silent=True) or req.text
            