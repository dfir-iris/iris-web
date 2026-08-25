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

from pathlib import Path
import re
import shutil
import time
import requests
from docker_compose import DockerCompose
from rest_api import RestApi
from server_timeout_error import ServerTimeoutError

API_URL = 'http://127.0.0.1:8000'
# Cookie-session routes need this, not API_URL: SESSION_COOKIE_SECURE=True (source/app/configuration.py)
# means Flask's session cookie is never sent back over plain HTTP, only through nginx/HTTPS.
HTTPS_URL = 'https://127.0.0.1'
_API_KEY = 'B8BA5D730210B50F41C06941582D7965D57319D5685440587F98DFDC45A01594'
_IRIS_PATH = Path('..')
_TEST_DATA_PATH = Path('./data')
# Matches IRIS_ADM_USERNAME (default) / IRIS_ADM_PASSWORD in tests/data/basic.env.
_ADMIN_USERNAME = 'administrator'
_ADMIN_PASSWORD = 'MySuperAdminPassword!'


class Iris:

    def __init__(self):
        self._docker_compose = DockerCompose(_IRIS_PATH, 'docker-compose.dev.yml')
        self._api = RestApi(API_URL, _API_KEY)

    def _wait(self, condition, attempts, sleep_duration=1):
        count = 0
        while not condition():
            time.sleep(sleep_duration)
            count += 1
            if count > attempts:
                print('Docker compose logs: ', self._docker_compose.extract_all_logs())
                raise ServerTimeoutError()

    def _wait_until_api_is_ready(self):
        self._wait(self._api.is_ready, 60)

    def start(self):
        # TODO it would be preferable to have a dedicated directory with the
        #      docker-compose.yml file, because for now, it will overwrite the
        #      .env file and development/tests contexts are mixed up. To do
        #      that, we should split the building phase of dockers from the
        #      execution phase of the docker-compose. We should minimize the
        #      docker-compose so that as few files as possible need to be
        #      copied. Also, we should try to use standard dockers as much as
        #      possible instead of having iris specific builds (for instance
        #      for the database)
        shutil.copy2(_TEST_DATA_PATH.joinpath('basic.env'), _IRIS_PATH.joinpath('.env'))
        self._docker_compose.start()
        print('Waiting for DFIR-IRIS to start...')
        self._wait_until_api_is_ready()

    def stop(self):
        self._docker_compose.stop()

    def get_api_version(self):
        return self._api.get('api/versions')

    def create_alert(self):
        body = {
            'alert_title': 'alert title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        return self._api.post('/alerts/add', body)

    def create_asset(self):
        body = {
            'asset_type_id': '9',
            'asset_name': 'admin_laptop',
        }
        return self._api.post('/case/assets/add', body)

    def create_case(self):
        body = {
            'case_name': 'case name',
            'case_description': 'description',
            'case_customer': 1,
            'case_soc_id': ''
        }
        response = self._api.post('/manage/cases/add', body)
        return response['data']

    def update_case(self, case_identifier, data):
        return self._api.post(f'/manage/cases/update/{case_identifier}', data)

    def get_cases(self):
        return self._api.get('/manage/cases/list')

    def get_cases_filter(self):
        return self._api.get('/manage/cases/filter')

    def get_authenticated_session(self):
        """Log in with a real cookie session (not the API key) for routes gated by @ac_requires(),
        which read session['permissions'] directly and 500 if authenticated via API key only.
        Must go through nginx/HTTPS (HTTPS_URL) -- SESSION_COOKIE_SECURE=True means the session
        cookie is dropped by the client on a plain-HTTP round trip against API_URL."""
        session = requests.Session()
        session.verify = False
        login_page = session.get(f'{HTTPS_URL}/login').text
        csrf_match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', login_page)
        if not csrf_match:
            raise ServerTimeoutError('Could not find CSRF token on login page')
        session.post(f'{HTTPS_URL}/login', data={
            'csrf_token': csrf_match.group(1),
            'username': _ADMIN_USERNAME,
            'password': _ADMIN_PASSWORD,
        })
        return session

    def get_html(self, session, path, case_id=None):
        params = {'cid': case_id} if case_id is not None else None
        response = session.get(f'{HTTPS_URL}{path}', params=params)
        return response.status_code, response.text
