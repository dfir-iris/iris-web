#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
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

STATISTICS_DASHBOARD_UUID = '00000000-0000-4000-8000-000000000001'

_CUSTOM_DASHBOARDS_READ = 0x1000
_CUSTOM_DASHBOARDS_WRITE = 0x2000
_CUSTOM_DASHBOARDS_SHARE = 0x4000


def _minimal_widget(name='widget'):
    return {
        'name': name,
        'chart_type': 'number',
        'fields': [{'table': 'alerts', 'column': 'alert_id', 'aggregation': 'count', 'alias': 'total'}],
    }


def _minimal_dashboard(name='dashboard'):
    return {
        'name': name,
        'description': 'test dashboard',
        'widgets': [_minimal_widget('total alerts')],
    }


class TestsRestCustomDashboards(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_list_dashboards_returns_seeded_statistics(self):
        response = self._subject.get('/api/v2/custom-dashboards').json()
        self.assertIn('data', response)
        uuids = [d['dashboard_uuid'] for d in response['data']]
        self.assertIn(STATISTICS_DASHBOARD_UUID, uuids)

    def test_seeded_statistics_dashboard_is_system(self):
        response = self._subject.get(f'/api/v2/custom-dashboards/{STATISTICS_DASHBOARD_UUID}').json()
        self.assertTrue(response['data'].get('is_system'))

    def test_create_dashboard_returns_201(self):
        response = self._subject.create('/api/v2/custom-dashboards', _minimal_dashboard('mine'))
        self.assertEqual(201, response.status_code)
        body = response.json()
        self.assertEqual('mine', body['data']['name'])
        self.assertFalse(body['data']['is_system'])

    def test_update_dashboard_returns_200(self):
        created = self._subject.create('/api/v2/custom-dashboards', _minimal_dashboard('first')).json()
        uuid = created['data']['dashboard_uuid']
        renamed = _minimal_dashboard('renamed')
        response = self._subject.update(f'/api/v2/custom-dashboards/{uuid}', renamed)
        self.assertEqual(200, response.status_code)
        self.assertEqual('renamed', response.json()['data']['name'])

    def test_delete_dashboard_succeeds(self):
        created = self._subject.create('/api/v2/custom-dashboards', _minimal_dashboard('todelete')).json()
        uuid = created['data']['dashboard_uuid']
        response = self._subject.delete(f'/api/v2/custom-dashboards/{uuid}')
        self.assertIn(response.status_code, (200, 204))
        follow_up = self._subject.get(f'/api/v2/custom-dashboards/{uuid}')
        self.assertEqual(404, follow_up.status_code)

    def test_update_system_dashboard_is_refused(self):
        renamed = _minimal_dashboard('hijacked')
        response = self._subject.update(f'/api/v2/custom-dashboards/{STATISTICS_DASHBOARD_UUID}', renamed)
        self.assertNotEqual(200, response.status_code)

    def test_delete_system_dashboard_is_refused(self):
        response = self._subject.delete(f'/api/v2/custom-dashboards/{STATISTICS_DASHBOARD_UUID}')
        self.assertNotEqual(200, response.status_code)
        self.assertNotEqual(204, response.status_code)

    def test_render_rejects_unknown_table(self):
        body = {
            'definition': {
                'name': 'evil',
                'widgets': [{
                    'name': 'bad',
                    'chart_type': 'number',
                    'fields': [{'table': 'pg_user', 'column': 'usename', 'aggregation': 'count', 'alias': 'x'}],
                }],
            }
        }
        response = self._subject.create(
            f'/api/v2/custom-dashboards/{STATISTICS_DASHBOARD_UUID}/render', body,
        )
        self.assertEqual(200, response.status_code)
        widgets = response.json()['data']['widgets']
        self.assertTrue(any('error' in w for w in widgets))

    def test_render_rejects_unknown_named_aggregation(self):
        body = {
            'definition': {
                'name': 'computed',
                'widgets': [{
                    'name': 'bad',
                    'chart_type': 'number',
                    'fields': [{'table': 'computed', 'column': 'no_such_metric', 'alias': 'x'}],
                }],
            }
        }
        response = self._subject.create(
            f'/api/v2/custom-dashboards/{STATISTICS_DASHBOARD_UUID}/render', body,
        )
        self.assertEqual(200, response.status_code)
        widgets = response.json()['data']['widgets']
        self.assertTrue(any('error' in w for w in widgets))

    def test_render_pie_chart_executes(self):
        body = {
            'definition': {
                'name': 'render-test',
                'widgets': [{
                    'name': 'alerts by severity',
                    'chart_type': 'pie',
                    'fields': [
                        {'table': 'severities', 'column': 'severity_name', 'alias': 'severity'},
                        {'table': 'alerts', 'column': 'alert_id', 'aggregation': 'count', 'alias': 'total'},
                    ],
                    'group_by': ['severities.severity_name'],
                }],
            }
        }
        response = self._subject.create(
            f'/api/v2/custom-dashboards/{STATISTICS_DASHBOARD_UUID}/render', body,
        )
        self.assertEqual(200, response.status_code)
        widgets = response.json()['data']['widgets']
        self.assertEqual(1, len(widgets))
        self.assertNotIn('error', widgets[0])

    def test_render_named_aggregation_returns_value(self):
        body = {
            'definition': {
                'name': 'mttd-test',
                'widgets': [{
                    'name': 'mttd',
                    'chart_type': 'number',
                    'fields': [{'table': 'computed', 'column': 'mttd_seconds', 'alias': 'mttd_seconds'}],
                }],
            }
        }
        response = self._subject.create(
            f'/api/v2/custom-dashboards/{STATISTICS_DASHBOARD_UUID}/render', body,
        )
        self.assertEqual(200, response.status_code)
        widgets = response.json()['data']['widgets']
        self.assertEqual('mttd_seconds', widgets[0].get('computed'))

    def test_schema_endpoint_lists_named_aggregations(self):
        response = self._subject.get('/api/v2/custom-dashboards/schema').json()
        agg_names = [a['name'] for a in response['data']['named_aggregations']]
        self.assertIn('mttd_seconds', agg_names)
        self.assertIn('mttr_seconds', agg_names)
        self.assertIn('false_positive_rate', agg_names)
        self.assertIn('escalation_rate', agg_names)
        self.assertIn('alerts_window_count', agg_names)

    def test_presets_endpoint_returns_entries(self):
        response = self._subject.get('/api/v2/custom-dashboards/presets').json()
        self.assertGreater(len(response['data']), 0)

    def test_unauthenticated_user_without_read_cannot_list(self):
        user = self._subject.create_dummy_user(permissions=0)
        response = user.get('/api/v2/custom-dashboards')
        self.assertEqual(403, response.status_code)

    def test_ownership_scoping_hides_other_users_unshared_dashboards(self):
        alice = self._subject.create_dummy_user(permissions=_CUSTOM_DASHBOARDS_READ | _CUSTOM_DASHBOARDS_WRITE)
        bob = self._subject.create_dummy_user(permissions=_CUSTOM_DASHBOARDS_READ | _CUSTOM_DASHBOARDS_WRITE)
        created = alice.create('/api/v2/custom-dashboards', _minimal_dashboard('alice-private')).json()
        uuid = created['data']['dashboard_uuid']
        response = bob.get(f'/api/v2/custom-dashboards/{uuid}')
        self.assertIn(response.status_code, (403, 404))

    def test_shared_dashboards_visible_to_other_users(self):
        alice = self._subject.create_dummy_user(
            permissions=_CUSTOM_DASHBOARDS_READ | _CUSTOM_DASHBOARDS_WRITE | _CUSTOM_DASHBOARDS_SHARE
        )
        bob = self._subject.create_dummy_user(permissions=_CUSTOM_DASHBOARDS_READ)
        payload = _minimal_dashboard('alice-shared')
        payload['is_shared'] = True
        created = alice.create('/api/v2/custom-dashboards', payload).json()
        uuid = created['data']['dashboard_uuid']
        response = bob.get(f'/api/v2/custom-dashboards/{uuid}')
        self.assertEqual(200, response.status_code)
