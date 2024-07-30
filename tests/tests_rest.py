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


def _get_case_with_identifier(response, identifier):
    for case in response['cases']:
        if identifier == case['case_id']:
            return case
    raise ValueError('Case not found')


class TestsRest(TestCase):
    _subject = None

    @classmethod
    def setUpClass(cls) -> None:
        cls._subject = Iris()
        cls._subject.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._subject.stop()

    def tearDown(self):
        cases = self._subject.get('/api/v2/cases', query_parameters={'per_page': 1000000000}).json()
        for case in cases['cases']:
            identifier = case['case_id']
            self._subject.delete(f'/api/v2/cases/{identifier}')

    def test_create_asset_should_not_fail(self):
        response = self._subject.create_asset()
        self.assertEqual('success', response['status'])

    def test_get_api_version_should_not_fail(self):
        response = self._subject.get_api_version()
        self.assertEqual('success', response['status'])

    def test_create_case_should_return_201(self):
        response = self._subject.create('/api/v2/cases', {
            'case_name': 'name',
            'case_description': 'description',
            'case_customer': 1,
            'case_soc_id': ''
        })
        self.assertEqual(201, response.status_code)

    def test_create_case_with_missing_name_should_return_400(self):
        response = self._subject.create('/api/v2/cases', {
            'case_description': 'description',
            'case_customer': 1,
            'case_soc_id': ''
        })
        self.assertEqual(400, response.status_code)

    def test_create_case_with_classification_id_should_set_classification_id(self):
        response = self._subject.create('/api/v2/cases', {
            'case_name': 'name',
            'case_description': 'description',
            'case_customer': 1,
            'case_soc_id': '',
            'classification_id': 2
        }).json()
        self.assertEqual(2, response['classification_id'])

    def test_create_case_should_add_a_new_case(self):
        response = self._subject.get_cases()
        initial_case_count = len(response['data'])
        self._subject.create_dummy_case()
        response = self._subject.get_cases()
        case_count = len(response['data'])
        self.assertEqual(initial_case_count + 1, case_count)

    def test_get_case_should_return_case_data(self):
        response = self._subject.create('/api/v2/cases', {
            'case_name': 'name',
            'case_description': 'description',
            'case_customer': 1,
            'case_soc_id': ''
        }).json()
        identifier = response['case_id']
        response = self._subject.get(f'/api/v2/cases/{identifier}').json()
        self.assertEqual('description', response['case_description'])

    def test_delete_case_should_return_204(self):
        response = self._subject.create('/api/v2/cases', {
            'case_name': 'name',
            'case_description': 'description',
            'case_customer': 1,
            'case_soc_id': ''
        }).json()
        identifier = response['case_id']
        response = self._subject.delete(f'/api/v2/cases/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_get_case_should_return_404_after_it_is_deleted(self):
        response = self._subject.create('/api/v2/cases', {
            'case_name': 'name',
            'case_description': 'description',
            'case_customer': 1,
            'case_soc_id': ''
        }).json()
        identifier = response['case_id']
        self._subject.delete(f'/api/v2/cases/{identifier}')
        response = self._subject.get(f'/api/v2/cases/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_update_case_should_not_require_case_name_issue_358(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.update_case(case_identifier, {'case_tags': 'test,example'})
        self.assertEqual('success', response['status'])

    def test_manage_case_filter_api_rest_should_fail(self):
        self._subject.create_dummy_case()
        response = self._subject.get_cases_filter()
        self.assertEqual('success', response['status'])

    def test_get_case_graph_should_not_fail(self):
        response = self._subject.get('/case/graph/getdata').json()
        self.assertEqual('success', response['status'])

    def test_get_ioc_should_not_fail(self):
        response = self._subject.get('/case/ioc/list').json()
        self.assertEqual('success', response['status'])

    def test_create_case_template_should_not_be_forbidden_to_administrator(self):
        query_parameters = {
            'cid': 1
        }
        body = {
            'case_template_json': '{"name": "Template name"}',
        }
        response = self._subject.create('/manage/case-templates/add', body, query_parameters=query_parameters)
        # TODO should really be 201 here
        self.assertEqual(200, response.status_code)

    def test_update_settings_should_not_fail(self):
        body = {}
        response = self._subject.create('/manage/settings/update', body)
        self.assertEqual(200, response.status_code)

    def test_create_ioc_should_return_good_ioc_type_id(self):
        case_identifier = self._subject.create_dummy_case()
        body = {"ioc_type_id": 1, "ioc_tlp_id": 2, "ioc_value": "8.8.8.8", "ioc_description": "rewrw", "ioc_tags": ""}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        self.assertEqual(1, response['ioc_type_id'])

    def test_get_ioc_should_return_ioc_type_id(self):
        ioc_type_id = 1
        case_identifier = self._subject.create_dummy_case()
        body = {"ioc_type_id": ioc_type_id, "ioc_tlp_id": 2, "ioc_value": "8.8.8.8", "ioc_description": "rewrw", "ioc_tags": ""}
        test = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        current_id = test['ioc_id']
        response = self._subject.get(f'/api/v2/iocs/{current_id}').json()
        self.assertEqual(ioc_type_id, response['ioc_type_id'])

    def test_get_ioc_with_missing_ioc_identifier_should_return_error(self):
        case_identifier = self._subject.create_dummy_case()
        body = {"ioc_type_id": 1, "ioc_tlp_id": 2, "ioc_value": "8.8.8.8", "ioc_description": "rewrw", "ioc_tags": ""}
        self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        test = self._subject.get(f'/api/v2/iocs/{None}').json()
        self.assertEqual('error', test['status'])

    def test_delete_ioc_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {"ioc_type_id": 1, "ioc_tlp_id": 2, "ioc_value": "8.8.8.8", "ioc_description": "rewrw", "ioc_tags": ""}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        ioc_identifier = response['ioc_id']
        response = self._subject.delete(f'/api/v2/iocs/{ioc_identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_ioc_with_missing_ioc_identifier_should_return_404(self):
        response = self._subject.delete('/api/v2/iocs/None')
        self.assertEqual(404, response.status_code)

    def test_create_alert_should_not_fail(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1
        }
        response = self._subject.create('/alerts/add', body)
        self.assertEqual(200, response.status_code)

    def test_alerts_filter_with_alerts_filter_should_not_fail(self):
        response = self._subject.get('/alerts/filter', query_parameters={'alert_assets': 'some assert name'})
        self.assertEqual(200, response.status_code)

    def test_alerts_filter_with_iocs_filter_should_not_fail(self):
        response = self._subject.get('/alerts/filter', query_parameters={'alert_iocs': 'some ioc value'})
        self.assertEqual(200, response.status_code)

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

    def test_get_timeline_state_should_return_200(self):
        response = self._subject.get('/case/timeline/state', query_parameters={'cid': 1})
        self.assertEqual(200, response.status_code)

    def test_add_task_should_return_201(self):
        case_identifier = self._subject.create_dummy_case()
        body = {"task_assignees_id": [1], "task_description": "", "task_status_id": 1, "task_tags": "", "task_title": "dummy title", "custom_attributes": {}}
        response = self._subject.add_tasks(case_identifier, body)
        self.assertEqual(201, response.status_code)

    def test_add_task_with_missing_task_title_identifier_should_return_400(self):
        case_identifier = self._subject.create_dummy_case()
        body = {"task_assignees_id": [1], "task_description": "", "task_status_id": 1, "task_tags": "", "custom_attributes": {}}
        response = self._subject.add_tasks(case_identifier, body)
        self.assertEqual(400, response.status_code)

    def test_get_tasks_should_return_dummy_title(self):
        case_identifier = self._subject.create_dummy_case()
        task_id = 2
        body = {"task_assignees_id": [task_id], "task_description": "", "task_status_id": 1, "task_tags": "", "task_title": "dummy title",
                "custom_attributes": {}}
        self._subject.add_tasks(case_identifier, body)
        response = self._subject.get_tasks(task_id).json()
        self.assertEqual("dummy title", response['task_title'])

    def test_get_tasks_with_missing_ioc_identifier_should_return_error(self):
        case_identifier = self._subject.create_dummy_case()
        task_id = 1
        body = {"task_assignees_id": [task_id], "task_description": "", "task_status_id": 1, "task_tags": "", "task_title": "dummy title", "custom_attributes": {}}
        self._subject.add_tasks(case_identifier, body)
        response = self._subject.get_tasks(None).json()
        self.assertEqual('error', response['status'])

    def test_delete_task_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        task_id = 1
        body = {"task_assignees_id": [task_id], "task_description": "", "task_status_id": 1, "task_tags": "", "task_title": "dummy title",
                "custom_attributes": {}}
        self._subject.add_tasks(case_identifier, body)
        test = self._subject.delete_tasks(task_id)
        self.assertEqual(204, test.status_code)

    def test_delete_task_with_missing_task_identifier_should_return_404(self):
        case_identifier = self._subject.create_dummy_case()
        task_id = 1
        body = {"task_assignees_id": [task_id], "task_description": "", "task_status_id": 1, "task_tags": "", "task_title": "dummy title",
                "custom_attributes": {}}
        self._subject.add_tasks(case_identifier, body)
        test = self._subject.delete_tasks(None)
        self.assertEqual(404, test.status_code)

    def test_get_cases_should_not_fail(self):
        response = self._subject.get('/api/v2/cases')
        self.assertEqual(200, response.status_code)

    def test_get_cases_should_filter_on_case_name(self):
        response = self._subject.create('/api/v2/cases', {
            'case_name': 'test_get_cases_should_filter_on_case_name',
            'case_description': 'description',
            'case_customer': 1,
            'case_soc_id': ''
        }).json()
        case_identifier = response['case_id']
        filters = {'case_name': 'test_get_cases_should_filter_on_case_name'}
        response = self._subject.get('/api/v2/cases', query_parameters=filters).json()
        identifiers = []
        for case in response['cases']:
            identifiers.append(case['case_id'])
        self.assertIn(case_identifier, identifiers)

    def test_get_cases_should_filter_on_is_open(self):
        case_identifier = self._subject.create_dummy_case()
        self._subject.create(f'/manage/cases/close/{case_identifier}', {})
        filters = {'is_open': 'true'}
        response = self._subject.get('/api/v2/cases', query_parameters=filters).json()
        identifiers = []
        for case in response['cases']:
            identifiers.append(case['case_id'])
        self.assertNotIn(case_identifier, identifiers)

    def test_get_users_should_return_200(self):
        response = self._subject.get('/manage/users/list')
        self.assertEqual(200, response.status_code)

    def test_get_users_should_return_403_for_user_without_rights(self):
        user = self._subject.create_dummy_user()
        response = user.get('/manage/users/list')
        self.assertEqual(403, response.status_code)

    def test_get_cases_should_return_the_state_name(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get('/api/v2/cases').json()
        case = _get_case_with_identifier(response, case_identifier)
        self.assertEqual('Open', case['state']['state_name'])

    def test_get_cases_should_return_the_owner_name(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get('/api/v2/cases').json()
        case = _get_case_with_identifier(response, case_identifier)
        self.assertEqual('administrator', case['owner']['user_name'])

    def test_get_case_should_have_field_case_name(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}').json()
        self.assertIn('case_name', response)

    def test_get_iocs_should_not_fail(self):
        response = self._subject.get('/api/v2/iocs')
        self.assertEqual(200, response.status_code)
