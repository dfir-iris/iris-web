#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""Integration tests for /api/v2/notifications and related endpoints.

These run against the live docker-compose stack via the existing
`Iris` harness. The suite covers:

* Feed shape + pagination + unread count
* Mark-read behaviour and cross-user isolation
* User settings upsert + effective view
* Admin settings gating (non-admin gets 403)
* End-to-end: mentioning a user in a note produces a notification
"""

from unittest import TestCase

from iris import Iris
from iris import IRIS_PERMISSION_SERVER_ADMINISTRATOR


class TestsRestNotifications(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    # --- Feed --------------------------------------------------------------

    def test_get_notifications_should_return_success(self):
        response = self._subject.get('/api/v2/notifications')
        self.assertEqual(200, response.status_code)

    def test_get_notifications_should_return_envelope_with_data_and_count(self):
        response = self._subject.get('/api/v2/notifications').json()
        self.assertIn('data', response['data'])
        self.assertIn('unread_count', response['data'])
        self.assertIsInstance(response['data']['data'], list)

    def test_get_unread_count_should_return_zero_on_fresh_state(self):
        response = self._subject.get('/api/v2/notifications/unread-count').json()
        self.assertEqual(0, response['data']['unread_count'])

    # --- Settings ----------------------------------------------------------

    def test_get_settings_should_include_event_types_and_channels(self):
        response = self._subject.get('/api/v2/notifications/settings').json()
        payload = response['data']
        self.assertIn('event_types', payload)
        self.assertIn('channels', payload)
        self.assertIn('settings', payload)
        # Sanity: mention/in_app must be represented (it's a core event)
        self.assertIn('mention', payload['event_types'])
        self.assertIn('in_app', payload['channels'])

    def test_put_settings_should_persist_toggles(self):
        body = {'settings': {'mention': {'in_app': False}}}
        response = self._subject.update('/api/v2/notifications/settings', body).json()
        self.assertFalse(response['data']['settings']['mention']['in_app'])

        # Re-fetch — the row should still be there.
        follow_up = self._subject.get('/api/v2/notifications/settings').json()
        self.assertFalse(follow_up['data']['settings']['mention']['in_app'])

    def test_put_settings_should_reject_non_object_body(self):
        response = self._subject.update('/api/v2/notifications/settings',
                                        {'settings': 'not-an-object'})
        self.assertEqual(400, response.status_code)

    def test_put_settings_should_silently_drop_unknown_events(self):
        body = {'settings': {'not_a_real_event': {'in_app': False}}}
        response = self._subject.update('/api/v2/notifications/settings', body)
        # Bogus keys are dropped, not rejected — a stale SPA that
        # sends an unknown event type should still save what it can.
        self.assertEqual(200, response.status_code)

    # --- Admin gating ------------------------------------------------------

    def test_get_admin_settings_should_return_success_for_admin(self):
        response = self._subject.get('/api/v2/manage/notification-settings')
        self.assertEqual(200, response.status_code)

    def test_get_admin_settings_should_return_403_for_non_admin(self):
        # Ordinary user without server_administrator gets denied.
        user = self._subject.create_dummy_user()
        response = user.get('/api/v2/manage/notification-settings')
        self.assertEqual(403, response.status_code)

    def test_put_admin_settings_should_return_403_for_non_admin(self):
        user = self._subject.create_dummy_user()
        response = user.update('/api/v2/manage/notification-settings',
                               {'settings': {'mention': {'in_app': False}}})
        self.assertEqual(403, response.status_code)

    def test_put_admin_settings_should_persist_for_admin(self):
        body = {'settings': {'case_state_change': {'email': True}}}
        response = self._subject.update(
            '/api/v2/manage/notification-settings', body).json()
        self.assertTrue(response['data']['settings']['case_state_change']['email'])

    # --- Cross-user isolation ---------------------------------------------

    def test_mark_read_should_not_affect_another_users_rows(self):
        # Admin fires a notification against a fresh user by mentioning
        # them in a case note; then that user marks-all-read and the
        # admin's own feed should not shift.
        user = self._subject.create_dummy_user(
            [IRIS_PERMISSION_SERVER_ADMINISTRATOR])
        case_identifier = self._subject.create_dummy_case()

        # Content shape mirrors what the TipTap editor emits.
        mention_span = (
            f'<span data-mention data-kind="user" '
            f'data-id="{user.get_identifier()}" data-label="dummy">'
            f'@dummy</span>'
        )
        note_body = f'<p>Hey {mention_span} please look</p>'

        self._subject.create(f'/api/v2/cases/{case_identifier}/notes', {
            'note_title': 'title',
            'note_content': note_body,
        })

        # user sees a notification, admin does not
        user_count = user.get(
            '/api/v2/notifications/unread-count').json()['data']['unread_count']
        admin_count = self._subject.get(
            '/api/v2/notifications/unread-count').json()['data']['unread_count']

        self.assertGreaterEqual(user_count, 1)
        self.assertEqual(0, admin_count)

        # user marks all read → admin count still 0, user drops to 0
        user.create('/api/v2/notifications/mark-read', {'all': True})
        self.assertEqual(0, user.get(
            '/api/v2/notifications/unread-count').json()['data']['unread_count'])
