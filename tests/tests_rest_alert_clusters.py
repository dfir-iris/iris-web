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
from iris import IRIS_PERMISSION_ALERTS_WRITE
from iris import IRIS_PERMISSION_ALERT_CLUSTERS_READ
from iris import IRIS_PERMISSION_ALERT_CLUSTERS_WRITE

_IDENTIFIER_FOR_NONEXISTENT_OBJECT = 123456789
_OPEN_STATUS_ID = 1  # seeded first by create_safe_alert_cluster_status


def _alert_body():
    return {
        'alert_title': 'title',
        'alert_severity_id': 4,
        'alert_status_id': 3,
        'alert_customer_id': 1,
    }


def _cluster_body(**overrides):
    body = {
        'cluster_title': 'Test cluster',
        'cluster_description': 'Grouping brute-force alerts',
        'cluster_status_id': _OPEN_STATUS_ID,
        'cluster_customer_id': 1,
    }
    body.update(overrides)
    return body


class TestsRestAlertClusters(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_create_cluster_should_return_201(self):
        response = self._subject.create('/api/v2/alert-clusters', _cluster_body())
        self.assertEqual(201, response.status_code)

    def test_create_cluster_persists_title(self):
        response = self._subject.create('/api/v2/alert-clusters', _cluster_body()).json()
        self.assertEqual('Test cluster', response['cluster_title'])

    def test_create_cluster_without_permission_returns_403(self):
        user = self._subject.create_dummy_user()
        response = user.create('/api/v2/alert-clusters', _cluster_body())
        self.assertEqual(403, response.status_code)

    def test_read_cluster_returns_200(self):
        created = self._subject.create('/api/v2/alert-clusters', _cluster_body()).json()
        response = self._subject.get(f'/api/v2/alert-clusters/{created["cluster_id"]}')
        self.assertEqual(200, response.status_code)

    def test_read_nonexistent_cluster_returns_404(self):
        response = self._subject.get(f'/api/v2/alert-clusters/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_update_cannot_change_customer_id(self):
        created = self._subject.create('/api/v2/alert-clusters', _cluster_body()).json()
        # Attempt to move to a different customer — must be silently stripped.
        response = self._subject.update(
            f'/api/v2/alert-clusters/{created["cluster_id"]}',
            {'cluster_customer_id': 9999, 'cluster_title': 'Renamed'}
        ).json()
        self.assertEqual(1, response['cluster_customer_id'])
        self.assertEqual('Renamed', response['cluster_title'])

    def test_delete_cluster_returns_204(self):
        created = self._subject.create('/api/v2/alert-clusters', _cluster_body()).json()
        response = self._subject.delete(f'/api/v2/alert-clusters/{created["cluster_id"]}')
        self.assertEqual(204, response.status_code)

    def test_add_alerts_attaches_alerts(self):
        alert = self._subject.create('/api/v2/alerts', _alert_body()).json()
        cluster = self._subject.create('/api/v2/alert-clusters', _cluster_body()).json()
        response = self._subject.create(
            f'/api/v2/alert-clusters/{cluster["cluster_id"]}/alerts',
            {'alert_ids': [alert['alert_id']]}
        )
        self.assertEqual(200, response.status_code)
        self.assertIn(alert['alert_id'], response.json()['alert_ids'])

    def test_add_alerts_rejects_cross_tenant_alert(self):
        # Different customer than the cluster — should not attach.
        other_customer = self._subject.create_dummy_customer()
        alert_body = _alert_body()
        alert_body['alert_customer_id'] = other_customer
        alert = self._subject.create('/api/v2/alerts', alert_body).json()
        cluster = self._subject.create('/api/v2/alert-clusters', _cluster_body()).json()
        response = self._subject.create(
            f'/api/v2/alert-clusters/{cluster["cluster_id"]}/alerts',
            {'alert_ids': [alert['alert_id']]}
        ).json()
        self.assertNotIn(alert['alert_id'], response['alert_ids'])

    def test_escalate_creates_case_and_updates_cluster(self):
        alert = self._subject.create('/api/v2/alerts', _alert_body()).json()
        cluster = self._subject.create('/api/v2/alert-clusters', _cluster_body()).json()
        self._subject.create(
            f'/api/v2/alert-clusters/{cluster["cluster_id"]}/alerts',
            {'alert_ids': [alert['alert_id']]}
        )
        response = self._subject.create(
            f'/api/v2/alert-clusters/{cluster["cluster_id"]}/escalate',
            {'case_title': 'Escalated cluster'}
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertIn('case_id', payload)
        self.assertIsNotNone(payload['case_id'])

    def test_escalate_empty_cluster_returns_error(self):
        cluster = self._subject.create('/api/v2/alert-clusters', _cluster_body()).json()
        response = self._subject.create(
            f'/api/v2/alert-clusters/{cluster["cluster_id"]}/escalate', {}
        )
        self.assertEqual(400, response.status_code)

    def test_list_clusters_filters_by_customer(self):
        self._subject.create('/api/v2/alert-clusters', _cluster_body(cluster_title='A'))
        self._subject.create('/api/v2/alert-clusters', _cluster_body(cluster_title='B'))
        response = self._subject.get(
            '/api/v2/alert-clusters', query_parameters={'customer_id': 1, 'per_page': 100}
        ).json()
        self.assertGreaterEqual(response['total'], 2)

    def test_user_without_read_permission_cannot_list(self):
        user = self._subject.create_dummy_user(permissions=IRIS_PERMISSION_ALERT_CLUSTERS_WRITE)
        response = user.get('/api/v2/alert-clusters')
        self.assertEqual(403, response.status_code)
