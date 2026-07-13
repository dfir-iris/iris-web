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

"""
Integration tests for the MFA hardening on the SPA auth endpoints.

These run against the docker-compose stack the rest of the suite uses.
They drive `/api/v2/auth/*` end-to-end so we exercise the JWT round-trip,
the central token gate in `_token_authentication_process`, and the
in-process throttle on `_mfa_throttle_*`.

Response shape note: the v2 auth endpoints use `response_api_success`
which serialises the data dict DIRECTLY as the HTTP body — no envelope
wrapping. So `tokens` and `mfa_required` sit at the top level of the
JSON, NOT under `body['data']`. Error envelope is HTTP 400 with body
`{message: "..."}` (no `status` field).

The tests flip the `enforce_mfa` server setting via the admin endpoint
where required and always restore it in `tearDown` — leaving MFA on
between tests would break every other suite in the project.
"""

from unittest import TestCase
from uuid import uuid4

import pyotp
import requests
from urllib import parse

from iris import Iris
from iris import API_URL


_PASSWORD = 'aA.1234567890'


def _login(username, password):
    """POST /api/v2/auth/login and return the parsed top-level JSON body.

    We bypass the `User.login()` helper so we can read fields that helper
    throws away (mfa_required, mfa_setup_complete, tokens).
    """
    url = parse.urljoin(API_URL, '/api/v2/auth/login')
    return requests.post(url, json={'username': username, 'password': password}).json()


def _refresh(refresh_token):
    url = parse.urljoin(API_URL, '/api/v2/auth/refresh-token')
    return requests.post(url, json={'refresh_token': refresh_token})


def _mfa_verify(refresh_token, token):
    url = parse.urljoin(API_URL, '/api/v2/auth/mfa-verify')
    return requests.post(url, json={'refresh_token': refresh_token, 'token': token})


def _mfa_setup(refresh_token, token, secret, password):
    url = parse.urljoin(API_URL, '/api/v2/auth/mfa-setup')
    return requests.post(
        url,
        json={
            'refresh_token': refresh_token,
            'token': token,
            'mfa_secret': secret,
            'user_password': password,
        },
    )


def _get_with_bearer(path, access_token):
    url = parse.urljoin(API_URL, path)
    return requests.get(url, headers={'Authorization': f'Bearer {access_token}'})


class TestsAuthMfa(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()
        # Snapshot enforce_mfa so each test starts from a known baseline
        # regardless of state left by other suites.
        self._set_enforce_mfa(False)

    def tearDown(self):
        # Always turn enforce_mfa OFF before clearing the DB — otherwise
        # the admin user we use to clean up gets locked into the MFA
        # flow on the next login.
        self._set_enforce_mfa(False)
        self._subject.clear_database()

    # ---------- helpers ----------

    def _set_enforce_mfa(self, value: bool):
        """Flip the global enforce_mfa flag via the admin settings PUT.

        The endpoint accepts a partial body, so we only send the one
        field we care about. The admin User in the scaffolding uses an
        API key, which bypasses the token MFA gate by design.
        """
        self._subject.update('/api/v2/manage/server/settings',
                             {'enforce_mfa': value})

    def _provision_mfa_user(self):
        """Create a user, log in once with MFA off, complete MFA setup,
        then turn enforce_mfa back on. Returns (user_name, totp_secret).

        We can't enable enforce_mfa first because the very first login
        (which yields the refresh token mfa-setup needs) would be a
        step-1 login and we'd have to drive the whole SPA flow manually.
        The end-state — user with mfa_setup_complete=True + enforce_mfa
        on — is what every MFA-required test below wants.
        """
        user_name = f'user{uuid4()}'
        self._subject.create_user(user_name, _PASSWORD)

        body = _login(user_name, _PASSWORD)
        refresh_token = body['tokens']['refresh_token']

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        setup_response = _mfa_setup(refresh_token, totp.now(), secret, _PASSWORD)
        self.assertEqual(200, setup_response.status_code)

        self._set_enforce_mfa(True)
        return user_name, secret

    # ---------- login response shape ----------

    def test_login_should_return_mfa_required_false_when_policy_off(self):
        user_name = f'user{uuid4()}'
        self._subject.create_user(user_name, _PASSWORD)
        body = _login(user_name, _PASSWORD)
        # SPA branches on this exact field — the rest of the auth flow
        # collapses if either key disappears from the response.
        self.assertIn('mfa_required', body)
        self.assertIn('mfa_setup_complete', body)
        self.assertFalse(body['mfa_required'])
        self.assertFalse(body['mfa_setup_complete'])

    def test_login_should_return_mfa_required_true_when_policy_on(self):
        user_name = f'user{uuid4()}'
        self._subject.create_user(user_name, _PASSWORD)
        self._set_enforce_mfa(True)
        body = _login(user_name, _PASSWORD)
        self.assertTrue(body['mfa_required'])
        self.assertFalse(body['mfa_setup_complete'])

    # ---------- central token gate ----------

    def test_step1_access_token_should_be_rejected_by_protected_endpoint(self):
        """The critical regression: an unverified step-1 token MUST NOT
        admit the caller to any `ac_api_requires` endpoint. If this ever
        passes 2xx again, the whole MFA flow is theatre."""
        user_name, _ = self._provision_mfa_user()
        body = _login(user_name, _PASSWORD)
        access_token = body['tokens']['access_token']
        response = _get_with_bearer('/api/v2/cases', access_token)
        self.assertEqual(401, response.status_code)

    def test_step1_access_token_should_be_rejected_by_whoami(self):
        """whoami uses @api_auth() rather than ac_api_requires — the gate
        sits in a different decorator, so we cover both paths."""
        user_name, _ = self._provision_mfa_user()
        body = _login(user_name, _PASSWORD)
        access_token = body['tokens']['access_token']
        response = _get_with_bearer('/api/v2/auth/whoami', access_token)
        self.assertEqual(401, response.status_code)

    def test_verified_access_token_should_admit_to_protected_endpoint(self):
        user_name, secret = self._provision_mfa_user()
        body = _login(user_name, _PASSWORD)
        refresh_token = body['tokens']['refresh_token']
        totp = pyotp.TOTP(secret)
        verify = _mfa_verify(refresh_token, totp.now()).json()
        access_token = verify['tokens']['access_token']
        response = _get_with_bearer('/api/v2/cases', access_token)
        self.assertEqual(200, response.status_code)

    # ---------- refresh propagation ----------

    def test_refresh_of_step1_token_should_stay_step1(self):
        """A step-1 refresh token MUST NOT be launderable into a verified
        access token by hitting /refresh-token. If the new access token
        admitted the caller, an attacker holding a stolen step-1 refresh
        could ride past the MFA challenge by refreshing once."""
        user_name, _ = self._provision_mfa_user()
        body = _login(user_name, _PASSWORD)
        refresh_token = body['tokens']['refresh_token']
        refreshed = _refresh(refresh_token).json()
        access_token = refreshed['tokens']['access_token']
        response = _get_with_bearer('/api/v2/cases', access_token)
        self.assertEqual(401, response.status_code)

    def test_refresh_of_verified_token_should_stay_verified(self):
        """The mirror case: a verified user's refresh keeps them verified,
        otherwise sessions would be lost every access-token expiry."""
        user_name, secret = self._provision_mfa_user()
        body = _login(user_name, _PASSWORD)
        refresh_token = body['tokens']['refresh_token']
        totp = pyotp.TOTP(secret)
        verify = _mfa_verify(refresh_token, totp.now()).json()
        verified_refresh = verify['tokens']['refresh_token']
        refreshed = _refresh(verified_refresh).json()
        access_token = refreshed['tokens']['access_token']
        response = _get_with_bearer('/api/v2/cases', access_token)
        self.assertEqual(200, response.status_code)

    # ---------- mfa-setup re-enrollment guard ----------

    def test_mfa_setup_should_refuse_to_overwrite_existing_enrollment(self):
        """An attacker holding a stolen step-1 refresh + the user's
        password must NOT be able to silently rebind MFA to their own
        device by re-running /mfa-setup. The error envelope is HTTP 400
        with `{message: "MFA already configured for this account"}`."""
        user_name, _ = self._provision_mfa_user()
        body = _login(user_name, _PASSWORD)
        refresh_token = body['tokens']['refresh_token']
        new_secret = pyotp.random_base32()
        new_totp = pyotp.TOTP(new_secret)
        response = _mfa_setup(refresh_token, new_totp.now(), new_secret, _PASSWORD)
        self.assertEqual(400, response.status_code)
        self.assertEqual('MFA already configured for this account',
                         response.json().get('message'))

    # ---------- brute-force throttle ----------

    def test_mfa_verify_should_lock_out_after_repeated_failures(self):
        """Five bad codes in a row should land the user in lockout. The
        sixth attempt — even with a valid code — must be refused so the
        6-digit space (10^6) stays infeasible to enumerate."""
        user_name, secret = self._provision_mfa_user()
        body = _login(user_name, _PASSWORD)
        refresh_token = body['tokens']['refresh_token']
        for _ in range(5):
            bad = _mfa_verify(refresh_token, '000000')
            self.assertEqual(400, bad.status_code)
        totp = pyotp.TOTP(secret)
        locked = _mfa_verify(refresh_token, totp.now())
        self.assertEqual(400, locked.status_code)
        # Message contains the remaining-time hint, which the SPA
        # surfaces verbatim to the user.
        self.assertIn('Too many MFA attempts',
                      locked.json().get('message', ''))
