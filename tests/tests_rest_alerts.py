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

_PERMISSION_ALERTS_DELETE = 0x10
_PERMISSION_ALERTS_WRITE = 0x8
_PERMISSION_ALERTS_READ = 0x4
_IDENTIFIER_FOR_NONEXISTENT_OBJECT = 123456789


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
        response = self._subject.create('/api/v2/alerts', body)
        self.assertEqual(201, response.status_code)

    def test_create_alert_should_return_data_alert_title(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        self.assertEqual('title', response['alert_title'])

    def test_create_alert_should_return_data_alert_severity_id(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        self.assertEqual(4, response['alert_severity_id'])

    def test_create_alert_should_return_data_alert_status_id(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        self.assertEqual(3, response['alert_status_id'])

    def test_create_alert_should_return_data_alert_customer_id(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        self.assertEqual(1, response['alert_customer_id'])

    def test_create_alert_should_return_400_when_alert_customer_id_is_missing(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
        }
        response = self._subject.create('/api/v2/alerts', body)
        self.assertEqual(400, response.status_code)

    def test_create_alert_should_return_403_when_user_has_no_permission_to_alert(self):
        user = self._subject.create_dummy_user()
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = user.create('/api/v2/alerts', body)
        self.assertEqual(403, response.status_code)

    def test_create_alert_should_return_field_classification_id_null_when_not_provided(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        self.assertIsNone(response['alert_classification_id'])

    def test_alerts_with_filter_alerts_assets_should_not_fail(self):
        response = self._subject.get('/api/v2/alerts', query_parameters={'alert_assets': 'some assert name'})
        self.assertEqual(200, response.status_code)

    def test_alerts_filter_with_filter_alert_iocs_should_not_fail(self):
        response = self._subject.get('api/v2/alerts', query_parameters={'alert_iocs': 'some ioc value'})
        self.assertEqual(200, response.status_code)

    def test_get_alerts_filter_should_show_newly_created_alert_for_administrator(self):
        alert_title = 'title_test'
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

    def test_create_customer_should_return_400_when_user_has_customer_alert_right(self):
        body = {
            'group_name': 'Customer create',
            'group_description': 'Group with customers can create alert',
            'group_permissions': [_PERMISSION_ALERTS_WRITE]
        }
        response = self._subject.create('/manage/groups/add', body).json()
        group_identifier = response['data']['group_id']
        user = self._subject.create_dummy_user()
        body = {'groups_membership': [group_identifier]}
        self._subject.create(f'/manage/users/{user.get_identifier()}/groups/update', body)

        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = user.create('/api/v2/alerts', body)
        self.assertEqual(400, response.status_code)

    def test_get_alert_should_return_200(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = self._subject.get(f'/api/v2/alerts/{identifier}')
        self.assertEqual(200, response.status_code)

    def test_get_alert_should_return_alert_title(self):
        alert_title = 'title_test'
        body = {
            'alert_title': alert_title,
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = self._subject.get(f'/api/v2/alerts/{identifier}').json()
        self.assertEqual(alert_title, response['alert_title'])

    def test_get_alert_should_return_alert_uuid(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        uuid = response['alert_uuid']
        response = self._subject.get(f'/api/v2/alerts/{identifier}').json()
        self.assertEqual(uuid, response['alert_uuid'])

    def test_get_alert_should_return_404_when_alert_not_found(self):
        response = self._subject.get(f'/api/v2/alerts/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_get_alert_should_return_403_when_user_has_no_permission_to_read_alert(self):
        user = self._subject.create_dummy_user()
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = user.get(f'/api/v2/alerts/{identifier}')
        self.assertEqual(403, response.status_code)

    def test_get_alert_should_return_404_when_user_has_no_customer_access(self):
        body = {
            'group_name': 'Customer create',
            'group_description': 'Group with customers can create alert',
            'group_permissions': [_PERMISSION_ALERTS_READ]
        }
        response = self._subject.create('/manage/groups/add', body).json()
        group_identifier = response['data']['group_id']
        user = self._subject.create_dummy_user()
        body = {'groups_membership': [group_identifier]}
        self._subject.create(f'/manage/users/{user.get_identifier()}/groups/update', body)

        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = user.get(f'/api/v2/alerts/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_update_alert_should_return_200(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = self._subject.update(f'/api/v2/alerts/{identifier}', {'alert_title': 'new_title'})
        self.assertEqual(200, response.status_code)

    def test_update_alert_should_return_alert_title(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        alert_title = 'new_title'
        response = self._subject.update(f'/api/v2/alerts/{identifier}', {'alert_title': alert_title}).json()
        self.assertEqual(alert_title, response['alert_title'])

    def test_update_alert_should_return_alert_uuid(self):
        alert_title = 'new_title'
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        uuid = response['alert_uuid']
        response = self._subject.update(f'/api/v2/alerts/{identifier}', {'alert_title': alert_title}).json()
        self.assertEqual(uuid, response['alert_uuid'])

    def test_update_alert_should_return_404_when_alert_not_found(self):
        response = self._subject.update(f'/api/v2/alerts/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}', {'alert_title': 'alert_title'})
        self.assertEqual(404, response.status_code)

    def test_update_alert_should_return_403_when_user_has_no_permission_to_read_alert(self):
        user = self._subject.create_dummy_user()
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = user.update(f'/api/v2/alerts/{identifier}', {})
        self.assertEqual(403, response.status_code)

    def test_update_alert_should_return_404_when_user_has_no_customer_access(self):
        body = {
            'group_name': 'Customer create',
            'group_description': 'Group with customers can create alert',
            'group_permissions': [_PERMISSION_ALERTS_WRITE]
        }
        response = self._subject.create('/manage/groups/add', body).json()
        group_identifier = response['data']['group_id']
        user = self._subject.create_dummy_user()
        body = {'groups_membership': [group_identifier]}
        self._subject.create(f'/manage/users/{user.get_identifier()}/groups/update', body)

        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = user.update(f'/api/v2/alerts/{identifier}', {'alert_title': 'new_title'})
        self.assertEqual(404, response.status_code)

    def test_update_alert_should_update_alert_context(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        alert_context = {'context_key': 'key'}
        response = self._subject.update(f'/api/v2/alerts/{identifier}', {'alert_context': alert_context}).json()
        self.assertEqual(alert_context, response['alert_context'])

    def test_update_alert_should_update_alert_source_content(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        alert_source_content = {
            '_id': '603f704aaf7417985bbf3b22',
            'contextId': '206e2965-6533-48a6-ba9e-794364a84bf9',
            'description': 'Contoso user performed 11 suspicious activities MITRE'
        }
        response = self._subject.update(f'/api/v2/alerts/{identifier}', {'alert_source_content': alert_source_content}).json()
        self.assertEqual(alert_source_content, response['alert_source_content'])

    def test_create_alert_should_return_asset_name_when_we_add_asset(self):
        asset_name = 'My super asset'
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
            'alert_assets': [{
            'asset_name': asset_name,
            'asset_description': 'Asset description',
            'asset_type_id': 1,
            'asset_ip': '1.1.1.1',
            'asset_domain': '',
            'asset_tags': 'tag1,tag2',
            }]
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        self.assertEqual(asset_name, response['assets'][0]['asset_name'])

    def test_create_alert_should_return_ioc_value_when_we_add_ioc(self):
        ioc_value = 'Tarzan 5'
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
            'alert_iocs': [{
                'ioc_value': ioc_value,
                'ioc_description': 'description of Tarzan',
                'ioc_tlp_id': 1,
                'ioc_type_id': 2,
                'ioc_tags': 'tag1,tag2',
            }]
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        self.assertEqual(ioc_value, response['iocs'][0]['ioc_value'])

    def test_delete_alert_should_return_204(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = self._subject.delete(f'/api/v2/alerts/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_alert_should_return_404_when_alert_not_found(self):
        response = self._subject.delete(f'/api/v2/alerts/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_delete_alert_should_return_403_when_user_has_no_permission_to_delete_alert(self):
        user = self._subject.create_dummy_user()
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = user.delete(f'/api/v2/alerts/{identifier}')
        self.assertEqual(403, response.status_code)

    def test_delete_alert_should_return_404_when_user_has_no_customer_access(self):
        body = {
            'group_name': 'Customer delete',
            'group_description': 'Group with customers can delete alert',
            'group_permissions': [_PERMISSION_ALERTS_DELETE]
        }
        response = self._subject.create('/manage/groups/add', body).json()
        group_identifier = response['data']['group_id']
        user = self._subject.create_dummy_user()
        body = {'groups_membership': [group_identifier]}
        self._subject.create(f'/manage/users/{user.get_identifier()}/groups/update', body)

        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = user.delete(f'/api/v2/alerts/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_get_alert_should_return_404_after_delete_alert(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        self._subject.delete(f'/api/v2/alerts/{identifier}')
        response = self._subject.get(f'/api/v2/alerts/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_get_related_alerts_should_return_200(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        response = self._subject.get(f'/api/v2/alerts/{identifier}/related-alerts')
        self.assertEqual(200, response.status_code)

    def test_get_related_alerts_should_return_two_alerts_identifier_in_iocs_table(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
            "alert_iocs": [{
                "ioc_value": "Tarzan 5",
                "ioc_description": "description of Tarzan",
                "ioc_tlp_id": 1,
                "ioc_type_id": 2,
                "ioc_tags": "tag1,tag2",
            }]
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier = response['alert_id']
        body = {
            'alert_title': 'title_2',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
            "alert_iocs": [{
                "ioc_value": "Tarzan 5",
                "ioc_description": "description of Tarzan",
                "ioc_tlp_id": 1,
                "ioc_type_id": 2,
                "ioc_tags": "tag1,tag2",
            }]
        }
        response = self._subject.create('api/v2/alerts', body).json()
        identifier2 = response['alert_id']
        response = self._subject.get(f'/api/v2/alerts/{identifier}/related-alerts').json()
        alert_ids=[identifier, identifier2]
        self.assertEqual(alert_ids, response['iocs'])