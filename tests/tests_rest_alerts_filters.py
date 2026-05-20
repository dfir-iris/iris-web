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

_IDENTIFIER_FOR_NONEXISTENT_OBJECT = 123456789


class TestsRestAlertsFilters(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_create_alert_filter_should_return_201(self):
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': 'filter name',
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }
        response = self._subject.create('/api/v2/alerts-filters', body)
        self.assertEqual(201, response.status_code)

    def test_create_alert_filter_should_return_400_when_filter_data_is_missing(self):
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': 'filter name',
            'filter_description': 'filter description',
        }
        response = self._subject.create('/api/v2/alerts-filters', body)
        self.assertEqual(400, response.status_code)

    def test_create_alert_filter_should_return_filter_type(self):
        filter_type = 'alerts'
        body = {
            'filter_is_private': 'true',
            'filter_type': filter_type,
            'filter_name': 'filter name',
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }
        response = self._subject.create('/api/v2/alerts-filters', body).json()
        self.assertEqual(filter_type, response['filter_type'])

    def test_create_alert_filter_should_return_filter_name(self):
        filter_name = 'name'
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': filter_name,
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }
        response = self._subject.create('/api/v2/alerts-filters', body).json()
        self.assertEqual(filter_name, response['filter_name'])

    def test_create_alert_filter_should_return_in_filter_data_alert_title(self):
        alert_title = 'alert_title'
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': 'filter_name',
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': alert_title,
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }
        response = self._subject.create('/api/v2/alerts-filters', body).json()
        self.assertEqual(alert_title, response['filter_data']['alert_title'])

    def test_get_alert_filter_should_return_200(self):
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': 'filter name',
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }

        response = self._subject.create('/api/v2/alerts-filters', body).json()
        identifier = response['filter_id']
        response = self._subject.get(f'/api/v2/alerts-filters/{identifier}')
        self.assertEqual(200, response.status_code)

    def test_get_alert_filter_should_return_filter_name(self):
        filter_name = 'filter name'
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': filter_name,
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }

        response = self._subject.create('/api/v2/alerts-filters', body).json()
        identifier = response['filter_id']
        response = self._subject.get(f'/api/v2/alerts-filters/{identifier}').json()
        self.assertEqual(filter_name, response['filter_name'])

    def test_get_alert_filter_should_return_404_when_alert_filter_not_found(self):
        response = self._subject.get(f'/api/v2/alerts-filters/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_get_alert_filter_should_return_404_when_user_has_not_created_alert_filter(self):
        user = self._subject.create_dummy_user()
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': 'filter_name',
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }

        response = self._subject.create('/api/v2/alerts-filters', body).json()
        identifier = response['filter_id']
        response = user.get(f'/api/v2/alerts-filters/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_update_alert_filter_should_return_200(self):
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': 'filter name',
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }

        response = self._subject.create('/api/v2/alerts-filters', body).json()
        identifier = response['filter_id']
        body = {
            'filter_name': 'filter name',
        }
        response = self._subject.update(f'/api/v2/alerts-filters/{identifier}', body)
        self.assertEqual(200, response.status_code)

    def test_update_alert_filter_should_return_filter_name(self):
        filter_name = 'new name'
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': 'old name',
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }

        response = self._subject.create('/api/v2/alerts-filters', body).json()
        identifier = response['filter_id']
        body = {
            'filter_name': filter_name,
        }
        response = self._subject.update(f'/api/v2/alerts-filters/{identifier}', body).json()
        self.assertEqual(filter_name, response['filter_name'])

    def test_update_alert_filter_should_return_filter_description(self):
        filter_description = 'new filter description'
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': 'old name',
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }

        response = self._subject.create('/api/v2/alerts-filters', body).json()
        identifier = response['filter_id']
        body = {
            'filter_description': filter_description,
        }
        response = self._subject.update(f'/api/v2/alerts-filters/{identifier}', body).json()
        self.assertEqual(filter_description, response['filter_description'])

    def test_update_alert_filter_should_return_filter_type(self):
        filter_type = 'new filter type'
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': 'old name',
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }

        response = self._subject.create('/api/v2/alerts-filters', body).json()
        identifier = response['filter_id']
        body = {
            'filter_type': filter_type,
        }
        response = self._subject.update(f'/api/v2/alerts-filters/{identifier}', body).json()
        self.assertEqual(filter_type, response['filter_type'])

    def test_update_alert_filter_should_return_filter_data_alert_title(self):
        alert_title = 'new alert title'
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': 'old name',
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }

        response = self._subject.create('/api/v2/alerts-filters', body).json()
        identifier = response['filter_id']
        body = {
            'filter_data':  {'alert_title': alert_title},
        }
        response = self._subject.update(f'/api/v2/alerts-filters/{identifier}', body).json()
        self.assertEqual(alert_title, response['filter_data']['alert_title'])

    def test_update_alert_filter_should_return_404_when_alert_filter_is_not_found(self):
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': 'old name',
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',
            }
        }

        response = self._subject.create('/api/v2/alerts-filters', body).json()
        body = {
            'filter_data':  {'alert_title': 'alert_title'},
        }
        response = self._subject.update(f'/api/v2/alerts-filters/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}', body)
        self.assertEqual(404, response.status_code)

    def test_delete_alert_filter_should_return_204(self):
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': 'old name',
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }

        response = self._subject.create('/api/v2/alerts-filters', body).json()
        identifier = response['filter_id']
        response = self._subject.delete(f'/api/v2/alerts-filters/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_alert_filter_should_return_404_when_alert_not_found(self):
        response = self._subject.delete(f'/api/v2/alerts-filters/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_get_alert_filter_should_return_404_after_delete_alert_filter(self):
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': 'old name',
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }

        response = self._subject.create('/api/v2/alerts-filters', body).json()
        identifier = response['filter_id']
        self._subject.delete(f'/api/v2/alerts-filters/{identifier}')
        response = self._subject.get(f'/api/v2/alerts-filters/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_update_alert_filter_should_return_400(self):
        body = {
            'filter_is_private': 'true',
            'filter_type': 'alerts',
            'filter_name': 'filter name',
            'filter_description': 'filter description',
            'filter_data': {
                'alert_title': 'filter name',
                'alert_description': '',
                'alert_source': '',
                'alert_tags': '',
                'alert_severity_id': '',
                'alert_start_date': '',
                'source_start_date': '',
                'source_end_date': '',
                'creation_end_date': '',
                'creation_start_date': '',
                'alert_assets': '',
                'alert_iocs': '',
                'alert_ids': '',
                'source_reference': '',
                'case_id': '',
                'custom_conditions': '',

            }
        }

        response = self._subject.create('/api/v2/alerts-filters', body).json()
        identifier = response['filter_id']
        body = {
            'filter_name': 1,
        }
        response = self._subject.update(f'/api/v2/alerts-filters/{identifier}', body)
        self.assertEqual(400, response.status_code)
