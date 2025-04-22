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
from uuid import uuid4


class TestsRestAlerts(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()
        response = self._subject.get('api/v2/alerts').json()
        for alert in response['data']:
            identifier = alert['alert_id']
            self._subject.create(f'/alerts/delete/{identifier}', {})

    def test_create_alert_should_return_201(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create(f'/api/v2/alerts', body)
        self.assertEqual(201, response.status_code)
    
    def test_create_alert_should_return_data_alert_title(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create(f'/api/v2/alerts', body).json()
        self.assertEqual('title', response['alert_title'])
    
    def test_create_alert_should_return_data_alert_severity_id(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create(f'/api/v2/alerts', body).json()
        self.assertEqual(4, response['alert_severity_id'])
    
    def test_create_alert_should_return_data_alert_status_id(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create(f'/api/v2/alerts', body).json()
        self.assertEqual(3, response['alert_status_id'])

    def test_create_alert_should_return_data_alert_customer_id(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create(f'/api/v2/alerts', body).json()
        self.assertEqual(1, response['alert_customer_id'])

    def test_create_alert_should_return_400_when_alert_customer_id_is_missing(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
        }
        response = self._subject.create(f'/api/v2/alerts', body)
        self.assertEqual(400, response.status_code)
    
    def test_create_alert_should_return_403_when_user_has_no_permission_to_alert(self):
        user = self._subject.create_dummy_user()
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = user.create(f'/api/v2/alerts', body)
        self.assertEqual(403, response.status_code)

    def test_create_alert_should_return_field_classification_id_null_when_not_provided(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create(f'/api/v2/alerts', body).json()
        self.assertIsNone(response['alert_classification_id'])

    def test_alerts_with_filter_alerts_assets_should_not_fail(self):
        response = self._subject.get('/api/v2/alerts', query_parameters={'alert_assets': 'some assert name'})
        self.assertEqual(200, response.status_code)

    def test_alerts_filter_with_filter_alert_iocs_should_not_fail(self):
        response = self._subject.get('api/v2/alerts', query_parameters={'alert_iocs': 'some ioc value'})
        self.assertEqual(200, response.status_code)

    def test_get_alerts_filter_should_show_newly_created_alert_for_administrator(self):
        alert_title = f'title{uuid4()}'
        body = {
            'alert_title': alert_title,
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        self._subject.create('/alerts/add', body)
        response = self._subject.get('/api/v2/alerts', query_parameters={'alert_title': alert_title}).json()
        self.assertEqual(1, response['total'])

    def test_get_alerts_should_return_field_data(self):
        response = self._subject.get('/api/v2/alerts').json()
        self.assertEqual([], response['data'])
    
    def test_get_alert_should_return_200(self):
        alert_title = f'title{uuid4()}'
        body = {
            'alert_title': alert_title,
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('/alerts/add', body).json()
        identifier = response['data']['alert_id']
        response = self._subject.get(f'/api/v2/alerts/{identifier}')
        self.assertEqual(200, response.status_code)

    def test_get_alert_should_return_400_when_alert_not_found(self):
        alert_title = f'title{uuid4()}'
        body = {
            'alert_title': alert_title,
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('/alerts/add', body).json()
        identifier = 'false'
        response = self._subject.get(f'/api/v2/alerts/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_merge_alert_into_a_case_should_not_fail(self):
        case_identifier = self._subject.create_dummy_case()
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('/alerts/add', body).json()
        alert_identifier = response['data']['alert_id']
        body = {
            'target_case_id': case_identifier,
            'iocs_import_list': [],
            'assets_import_list': []
        }
        response = self._subject.create(f'/alerts/merge/{alert_identifier}', body)
        # TODO should be 201
        self.assertEqual(200, response.status_code)
