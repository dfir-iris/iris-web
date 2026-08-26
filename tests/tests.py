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


class Tests(TestCase):
    _subject = None
    _ioc_count = 0
    _user_count = 0

    @classmethod
    def setUpClass(cls) -> None:
        cls._subject = Iris()
        cls._subject.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._subject.stop()

    # Note: this method is necessary because the state of the database is not reset between each test
    #       and we want to work with distinct object in each test
    @classmethod
    def _generate_new_dummy_ioc_value(cls):
        cls._ioc_count += 1
        return f'IOC value #{cls._ioc_count}'

    # Note: this method is necessary because the state of the database is not reset between each test
    #       and we want to work with distinct object in each test
    @classmethod
    def _generate_new_dummy_user_name(cls):
        cls._user_count += 1
        return f'user{cls._user_count}'

    def test_create_asset_should_not_fail(self):
        response = self._subject.create_asset()
        self.assertEqual('success', response['status'])

    def test_get_api_version_should_not_fail(self):
        response = self._subject.get_api_version()
        self.assertEqual('success', response['status'])

    def test_create_case_should_add_a_new_case(self):
        response = self._subject.get_cases()
        initial_case_count = len(response['data'])
        self._subject.create_case()
        response = self._subject.get_cases()
        case_count = len(response['data'])
        self.assertEqual(initial_case_count + 1, case_count)

    def test_update_case_should_not_require_case_name_issue_358(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        response = self._subject.update_case(case_identifier, {'case_tags': 'test,example'})
        self.assertEqual('success', response['status'])

    def test_custom_dashboard_case_child_table_widgets_are_not_affected_by_merged_alert_count(self):
        dashboard_payload = {
            'name': 'Regression dashboard - issue 1112',
            'widgets': [
                {
                    'name': 'Total Tasks',
                    'chart_type': 'number',
                    'fields': [{'table': 'case_tasks', 'column': 'id', 'aggregation': 'count', 'alias': 'total'}],
                },
                {
                    'name': 'Tasks per Case',
                    'chart_type': 'table',
                    'fields': [
                        {'table': 'cases', 'column': 'name', 'alias': 'case_name'},
                        {'table': 'case_tasks', 'column': 'task_title', 'alias': 'task_title'},
                    ],
                },
            ],
        }
        response = self._subject._api.post('/custom-dashboards/api/dashboards', dashboard_payload)
        self.assertEqual('success', response['status'])
        dashboard_id = response['data']['id']

        def fetch_widgets():
            response = self._subject._api.get(f'/custom-dashboards/api/dashboards/{dashboard_id}/data')
            return response['data']['widgets']

        # Baseline before adding our own data -- the suite's database is not reset between
        # tests, so asserting on a delta (not an absolute count) keeps this robust regardless
        # of what other tests have already created.
        baseline_total_tasks = fetch_widgets()[0]['data']['value']

        # Mirrors the exact reproduction from issue #1112: 4 cases with 1 task each, merged
        # into 0/2/2/1 alerts respectively. Pre-fix, the widget engine's query was always
        # rooted at `alerts`, so a case with 0 merged alerts never produced a base row
        # (invisible) and a case with N merged alerts produced N duplicate base rows (its
        # task counted N times): 0+2+2+1=5, not the true count of 4.
        case_ids = []
        case_names = []
        for _ in range(4):
            case = self._subject.create_case()
            case_ids.append(case['case_id'])
            case_names.append(case['case_name'])
            task_body = {'task_title': 'Regression task', 'task_status_id': 1, 'task_assignees_id': [1]}
            response = self._subject._api.post('/case/tasks/add', task_body, query_parameters={'cid': case['case_id']})
            self.assertEqual('success', response['status'])

        for case_index, alert_count in [(1, 2), (2, 2), (3, 1)]:
            target_case_id = case_ids[case_index]
            for _ in range(alert_count):
                alert = self._subject.create_alert()
                alert_id = alert['data']['alert_id']
                merge_body = {
                    'target_case_id': target_case_id,
                    'iocs_import_list': [],
                    'assets_import_list': [],
                    'import_as_event': False,
                }
                response = self._subject._api.post(f'/alerts/merge/{alert_id}', merge_body)
                self.assertEqual('success', response['status'])

        widgets = fetch_widgets()
        self.assertEqual(baseline_total_tasks + 4, widgets[0]['data']['value'])

        table_rows = widgets[1]['data']['source_rows']
        rows_for_my_cases = [row for row in table_rows if row['case_name'] in case_names]
        self.assertEqual(4, len(rows_for_my_cases))
        for row in rows_for_my_cases:
            self.assertEqual('Regression task', row['task_title'])