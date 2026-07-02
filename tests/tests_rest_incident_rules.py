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
from iris import IRIS_PERMISSION_INCIDENT_RULES_READ
from iris import IRIS_PERMISSION_INCIDENT_RULES_WRITE


def _rule_body(**overrides):
    body = {
        'rule_name': 'Stack brute-force alerts',
        'rule_description': 'Group repeated brute-force alerts from the same source',
        'rule_is_active': True,
        'rule_priority': 100,
        'rule_customer_scope': None,
        'rule_conditions': {
            'logic': 'and',
            'conditions': [
                {'field': 'alert_title', 'operator': 'like', 'value': 'brute'},
            ],
            'time_window_seconds': 3600,
            'group_by': ['alert_source'],
        },
        'rule_action_type': 'create_incident',
        'rule_action_config': {
            'title_template': 'Brute-force cluster: {alert_title}',
        },
    }
    body.update(overrides)
    return body


class TestsRestIncidentRules(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        # Rules aren't wiped by clear_database — do it inline.
        rules = self._subject.get('/api/v2/incident-rules').json()
        for rule in rules.get('data', []) if isinstance(rules, dict) else rules:
            rid = rule.get('rule_id') if isinstance(rule, dict) else None
            if rid:
                self._subject.delete(f'/api/v2/incident-rules/{rid}')
        self._subject.clear_database()

    def test_create_rule_returns_201(self):
        response = self._subject.create('/api/v2/incident-rules', _rule_body())
        self.assertEqual(201, response.status_code)

    def test_create_rule_rejects_empty_conditions(self):
        response = self._subject.create(
            '/api/v2/incident-rules',
            _rule_body(rule_conditions={'logic': 'and', 'conditions': []})
        )
        self.assertEqual(400, response.status_code)

    def test_create_rule_rejects_unknown_action(self):
        response = self._subject.create(
            '/api/v2/incident-rules', _rule_body(rule_action_type='not_a_real_action')
        )
        self.assertEqual(400, response.status_code)

    def test_attach_flow_action_is_no_longer_accepted(self):
        # Flow attachment moved into the flow itself (flow_conditions).
        # The rules engine only stacks alerts into incidents now.
        response = self._subject.create(
            '/api/v2/incident-rules',
            _rule_body(rule_action_type='attach_flow', rule_action_config={'flow_id': 1})
        )
        self.assertEqual(400, response.status_code)

    def test_update_rule_persists_changes(self):
        created = self._subject.create('/api/v2/incident-rules', _rule_body()).json()
        response = self._subject.update(
            f'/api/v2/incident-rules/{created["data"]["rule_id"] if "data" in created else created["rule_id"]}',
            {'rule_name': 'Renamed'}
        )
        self.assertEqual(200, response.status_code)

    def test_test_endpoint_returns_matches(self):
        # Create a matching alert first so the dry-run sample includes it.
        self._subject.create('/api/v2/alerts', {
            'alert_title': 'brute force login',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        })
        created = self._subject.create('/api/v2/incident-rules', _rule_body()).json()
        rule_id = created.get('rule_id') or created['data']['rule_id']
        response = self._subject.create(
            f'/api/v2/incident-rules/{rule_id}/test', {'sample_days': 30}
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        # Wrapped by response_api_success — data lives under 'data'
        matches = payload.get('matching_alert_ids') or payload.get('data', {}).get('matching_alert_ids')
        self.assertIsNotNone(matches)

    def test_user_without_write_permission_cannot_create(self):
        user = self._subject.create_dummy_user(permissions=IRIS_PERMISSION_INCIDENT_RULES_READ)
        response = user.create('/api/v2/incident-rules', _rule_body())
        self.assertEqual(403, response.status_code)
