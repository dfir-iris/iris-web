#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

from unittest import TestCase, skip
from uuid import uuid4
import requests
from urllib import parse

from iris import Iris
from iris import API_URL


class TestsAuth(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_login_should_redirect_to_dashboard(self):
        user_name = f'user{uuid4()}'
        password = 'aA.1234567890'
        # TODO would probably be nicer to put the login code on the user and login with it directly
        self._subject.create_user(user_name, password)
        url = parse.urljoin(API_URL, '/login')
        response = requests.post(url,
                                 allow_redirects=False,
                                 headers={'Content-Type': 'application/x-www-form-urlencoded'},
                                 data={'username': user_name, 'password': password})
        self.assertEqual('/dashboard?cid=1', response.headers['Location'])

    def test_login_should_not_redirect_to_external_site_open_redirect(self):
        user_name = f'user{uuid4()}'
        password = 'aA.1234567890'
        # TODO would probably be nicer to put the login code on the user and login with it directly
        self._subject.create_user(user_name, password)
        url = parse.urljoin(API_URL, '/login')
        response = requests.post(url,
                                 allow_redirects=False,
                                 headers={'Content-Type': 'application/x-www-form-urlencoded'},
                                 data={'username': user_name, 'password': password},
                                 params={'next': 'https:///www.google.com'})
        self.assertEqual('/dashboard?cid=1', response.headers['Location'])

    def test_login_should_return_authentication_cookie(self):
        user_name = f'user{uuid4()}'
        password = 'aA.1234567890'
        self._subject.create_user(user_name, password)
        url = parse.urljoin(API_URL, '/auth/login')
        response = requests.post(url, json={'username': user_name, 'password': password})
        self.assertIn('Set-Cookie', response.headers)

    def test_login_should_return_authentication_cookie_which_allows_get_requests(self):
        user_name = f'user{uuid4()}'
        password = 'aA.1234567890'
        self._subject.create_user(f'user{uuid4()}', password)
        url = parse.urljoin(API_URL, '/api/v2/auth/login')
        response = requests.post(url, json={'username': user_name, 'password': password})
        url = parse.urljoin(API_URL, '/api/v2/cases')
        name, value = response.headers['Set-Cookie'].split('=', 1)
        cookies = {
            name: value
        }
        response = requests.get(url, cookies=cookies)
        self.assertEqual(200, response.status_code)

    @skip
    def test_logout_should_forbid_later_requests_from_the_same_user(self):
        password = 'aA.1234567890'
        user = self._subject.create_user(f'user{uuid4()}', password)
        url = parse.urljoin(API_URL, '/api/v2/auth/login')
        response = requests.post(url, json={'username': user.get_login(), 'password': password})
        name, value = response.headers['Set-Cookie'].split('=', 1)
        cookies = {name: value}
        url = parse.urljoin(API_URL, '/api/v2/auth/logout')
        requests.get(url, cookies=cookies)
        url = parse.urljoin(API_URL, '/api/v2/cases')
        response = requests.get(url, cookies=cookies)
        self.assertEqual(401, response.status_code)