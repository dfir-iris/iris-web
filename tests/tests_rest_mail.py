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

"""Integration tests for /api/v2/manage/mail and mail config on
/api/v2/manage/server.

Covers rules CRUD (including admin gating), ingest-log read, mail
config round-trip on server settings (password write-only + set
flag), and the SMTP test-send endpoint's "SMTP not configured"
error path (we can't test successful SMTP delivery from the
integration harness without a real relay).
"""

from unittest import TestCase

from iris import Iris


class TestsRestMail(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        # Clean up rules we created — the harness doesn't wipe them.
        rules = self._subject.get('/api/v2/manage/mail/rules').json()
        if rules.get('data', {}).get('data'):
            for rule in rules['data']['data']:
                self._subject.delete(
                    f"/api/v2/manage/mail/rules/{rule['id']}")
        self._subject.clear_database()

    # --- Rules CRUD -------------------------------------------------------

    def test_list_rules_returns_empty_list_on_fresh_state(self):
        response = self._subject.get('/api/v2/manage/mail/rules').json()
        self.assertEqual([], response['data']['data'])

    def test_create_rule_persists_and_returns_the_row(self):
        body = {
            'name': 'catch-all',
            'priority': 500,
            'action': 'create_alert',
            'match_subject_regex': r'^alerts',
        }
        response = self._subject.create('/api/v2/manage/mail/rules', body).json()
        self.assertEqual('catch-all', response['data']['name'])
        self.assertEqual(500, response['data']['priority'])
        self.assertEqual('create_alert', response['data']['action'])

    def test_create_rule_rejects_missing_name(self):
        response = self._subject.create('/api/v2/manage/mail/rules',
                                        {'action': 'create_alert'})
        self.assertEqual(400, response.status_code)

    def test_create_rule_rejects_unknown_action(self):
        body = {'name': 'bad', 'action': 'launch_missiles'}
        response = self._subject.create('/api/v2/manage/mail/rules', body)
        self.assertEqual(400, response.status_code)

    def test_update_rule_writes_the_change(self):
        created = self._subject.create('/api/v2/manage/mail/rules',
                                       {'name': 'edit-me',
                                        'action': 'create_alert'}).json()
        rule_id = created['data']['id']
        response = self._subject.update(
            f'/api/v2/manage/mail/rules/{rule_id}',
            {'name': 'edited', 'enabled': False}).json()
        self.assertEqual('edited', response['data']['name'])
        self.assertFalse(response['data']['enabled'])

    def test_delete_rule_removes_it(self):
        created = self._subject.create('/api/v2/manage/mail/rules',
                                       {'name': 'gone-soon',
                                        'action': 'drop'}).json()
        rule_id = created['data']['id']
        response = self._subject.delete(
            f'/api/v2/manage/mail/rules/{rule_id}')
        self.assertEqual(200, response.status_code)
        # A follow-up GET should now 404
        response = self._subject.get(f'/api/v2/manage/mail/rules/{rule_id}')
        self.assertEqual(404, response.status_code)

    # --- Admin gating ------------------------------------------------------

    def test_list_rules_returns_403_for_non_admin(self):
        user = self._subject.create_dummy_user()
        response = user.get('/api/v2/manage/mail/rules')
        self.assertEqual(403, response.status_code)

    def test_create_rule_returns_403_for_non_admin(self):
        user = self._subject.create_dummy_user()
        response = user.create('/api/v2/manage/mail/rules',
                               {'name': 'x', 'action': 'drop'})
        self.assertEqual(403, response.status_code)

    # --- Ingest log --------------------------------------------------------

    def test_ingest_log_is_empty_on_fresh_state(self):
        response = self._subject.get(
            '/api/v2/manage/mail/ingest-log').json()
        self.assertEqual([], response['data']['data'])

    def test_ingest_log_returns_403_for_non_admin(self):
        user = self._subject.create_dummy_user()
        response = user.get('/api/v2/manage/mail/ingest-log')
        self.assertEqual(403, response.status_code)

    # --- Server settings — mail config -----------------------------------

    def test_mail_settings_included_in_server_settings_response(self):
        response = self._subject.get('/api/v2/manage/server/settings').json()
        # The mail columns default to safe values (disabled). We assert
        # only that the keys exist — the actual defaults are what the
        # migration wrote and covered in the schema tests.
        settings = response['data']['settings']
        self.assertIn('mail_smtp_enabled', settings)
        self.assertIn('mail_imap_enabled', settings)
        # Password fields must NOT be returned even if set
        self.assertNotIn('mail_smtp_password', settings)
        self.assertNotIn('mail_imap_password', settings)
        # …but the *_password_set booleans should be there so the SPA
        # can render placeholder inputs.
        self.assertIn('mail_smtp_password_set', settings)
        self.assertIn('mail_imap_password_set', settings)

    def test_smtp_password_write_never_leaks_back(self):
        # Setting a password via PUT should mark `_password_set`
        # True on the next GET but never return the ciphertext or
        # plaintext.
        self._subject.update('/api/v2/manage/server/settings', {
            'mail_smtp_enabled': True,
            'mail_smtp_host': 'smtp.example.com',
            'mail_smtp_port': 587,
            'mail_smtp_user': 'iris',
            'mail_smtp_password': 'p@ss w0rd!',
            'mail_from_address': 'iris@example.com',
        })
        response = self._subject.get(
            '/api/v2/manage/server/settings').json()
        settings = response['data']['settings']
        self.assertTrue(settings['mail_smtp_password_set'])
        self.assertNotIn('mail_smtp_password', settings)

    def test_test_send_returns_400_when_smtp_not_configured(self):
        # No SMTP config → the endpoint refuses to fake a delivery.
        # Reset any prior config left over from other tests first.
        self._subject.update('/api/v2/manage/server/settings', {
            'mail_smtp_enabled': False,
        })
        response = self._subject.create(
            '/api/v2/manage/server/mail/test-send',
            {'to': 'someone@example.com'})
        self.assertEqual(400, response.status_code)

    def test_test_send_rejects_bad_recipient(self):
        response = self._subject.create(
            '/api/v2/manage/server/mail/test-send',
            {'to': 'not-an-email'})
        self.assertEqual(400, response.status_code)

    def test_test_send_returns_403_for_non_admin(self):
        user = self._subject.create_dummy_user()
        response = user.create('/api/v2/manage/server/mail/test-send',
                               {'to': 'x@y.com'})
        self.assertEqual(403, response.status_code)
