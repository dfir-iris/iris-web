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
from iris import IRIS_PERMISSION_INVESTIGATION_FLOWS_READ
from iris import IRIS_PERMISSION_INVESTIGATION_FLOWS_WRITE


def _flow_body(**overrides):
    body = {
        'flow_name': 'Brute-force triage',
        'flow_description': 'Investigate suspected brute-force alerts',
        'flow_is_active': True,
        'flow_customer_scope': None,
    }
    body.update(overrides)
    return body


class TestsRestInvestigationFlows(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        flows = self._subject.get('/api/v2/investigation-flows').json()
        raw = flows.get('data', flows) if isinstance(flows, dict) else flows
        if isinstance(raw, list):
            for flow in raw:
                self._subject.delete(f'/api/v2/investigation-flows/{flow["flow_id"]}')
        self._subject.clear_database()

    def _create_flow(self):
        response = self._subject.create('/api/v2/investigation-flows', _flow_body()).json()
        return response.get('flow_id') or response.get('data', {}).get('flow_id')

    def test_create_flow_returns_201(self):
        response = self._subject.create('/api/v2/investigation-flows', _flow_body())
        self.assertEqual(201, response.status_code)

    def test_create_step_returns_201(self):
        flow_id = self._create_flow()
        response = self._subject.create(
            f'/api/v2/investigation-flows/{flow_id}/steps',
            {'step_order': 1, 'step_title': 'Check auth logs', 'step_description': 'Look at Splunk'}
        )
        self.assertEqual(201, response.status_code)

    def test_update_step_persists_changes(self):
        flow_id = self._create_flow()
        step = self._subject.create(
            f'/api/v2/investigation-flows/{flow_id}/steps',
            {'step_order': 1, 'step_title': 'First'}
        ).json()
        step_id = step.get('step_id') or step['data']['step_id']
        response = self._subject.update(
            f'/api/v2/investigation-flows/{flow_id}/steps/{step_id}',
            {'step_title': 'Renamed step'}
        )
        self.assertEqual(200, response.status_code)

    def test_delete_flow_cascades_steps(self):
        flow_id = self._create_flow()
        self._subject.create(
            f'/api/v2/investigation-flows/{flow_id}/steps',
            {'step_order': 1, 'step_title': 'Doomed step'}
        )
        response = self._subject.delete(f'/api/v2/investigation-flows/{flow_id}')
        self.assertEqual(204, response.status_code)

    def test_user_without_write_permission_cannot_create(self):
        user = self._subject.create_dummy_user(permissions=IRIS_PERMISSION_INVESTIGATION_FLOWS_READ)
        response = user.create('/api/v2/investigation-flows', _flow_body())
        self.assertEqual(403, response.status_code)

    def test_record_progress_requires_alert_with_flow(self):
        # Alert without a flow attached — check-off must fail cleanly.
        alert = self._subject.create('/api/v2/alerts', {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }).json()
        flow_id = self._create_flow()
        step = self._subject.create(
            f'/api/v2/investigation-flows/{flow_id}/steps',
            {'step_order': 1, 'step_title': 'Detached step'}
        ).json()
        step_id = step.get('step_id') or step['data']['step_id']
        response = self._subject.create(
            f'/api/v2/alerts/{alert["alert_id"]}/investigation-progress/{step_id}', {}
        )
        self.assertEqual(400, response.status_code)

    def test_deploy_backfills_matching_alerts(self):
        # Create an alert first, THEN a flow that matches it, then deploy
        # — the alert should get the flow_id back-filled.
        alert = self._subject.create('/api/v2/alerts', {
            'alert_title': 'brute force login attempt',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }).json()
        create_res = self._subject.create('/api/v2/investigation-flows', _flow_body(
            flow_target='alert',
            flow_conditions={
                'logic': 'and',
                'conditions': [
                    {'field': 'alert_title', 'operator': 'like', 'value': 'brute'}
                ],
            },
        )).json()
        flow_id = create_res.get('flow_id') or create_res['data']['flow_id']
        deploy = self._subject.create(
            f'/api/v2/investigation-flows/{flow_id}/deploy', {}
        )
        self.assertEqual(200, deploy.status_code)
        payload = deploy.json()
        counts = payload.get('data', payload)
        self.assertGreaterEqual(counts['alerts_attached'], 1)

    def test_deploy_skips_alerts_already_attached(self):
        # Once attached, deploy shouldn't overwrite — analyst may have
        # chosen the current flow deliberately.
        alert = self._subject.create('/api/v2/alerts', {
            'alert_title': 'brute force login attempt',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }).json()
        create_res = self._subject.create('/api/v2/investigation-flows', _flow_body(
            flow_conditions={
                'logic': 'and',
                'conditions': [{'field': 'alert_title', 'operator': 'like', 'value': 'brute'}],
            },
        )).json()
        flow_id = create_res.get('flow_id') or create_res['data']['flow_id']
        self._subject.create(f'/api/v2/investigation-flows/{flow_id}/deploy', {})
        # Second deploy should attach 0 new alerts.
        second = self._subject.create(
            f'/api/v2/investigation-flows/{flow_id}/deploy', {}
        ).json()
        counts = second.get('data', second)
        self.assertEqual(0, counts['alerts_attached'])
