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
Integration tests for `/api/v2/me/followed-cases` and the related
`/api/v2/cases/<id>/followers` endpoint.

Hits the docker-compose stack with the existing `Iris` test helper so
the JWT round-trip, access-control gate, and DB cascades are all
exercised end-to-end. Response shape mirrors the rest of the v2 API:
`response_api_success` ships the data dict directly as the JSON body
(no envelope), `response_api_error` returns HTTP 400 with
`{message: "..."}`.
"""

from unittest import TestCase

from iris import Iris


class TestsRestFollowedCases(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_follow_case_should_return_201_and_list_should_include_it(self):
        case_id = self._subject.create_dummy_case()
        response = self._subject.create('/api/v2/me/followed-cases', {'case_id': case_id})
        self.assertEqual(201, response.status_code)

        listed = self._subject.get('/api/v2/me/followed-cases').json()
        ids = [c['case_id'] for c in listed]
        self.assertIn(case_id, ids)

    def test_follow_case_twice_should_be_idempotent(self):
        case_id = self._subject.create_dummy_case()
        first = self._subject.create('/api/v2/me/followed-cases', {'case_id': case_id})
        second = self._subject.create('/api/v2/me/followed-cases', {'case_id': case_id})
        self.assertEqual(201, first.status_code)
        self.assertEqual(201, second.status_code)

        listed = self._subject.get('/api/v2/me/followed-cases').json()
        # An idempotent re-follow must not create a duplicate row.
        followed_for_case = [c for c in listed if c['case_id'] == case_id]
        self.assertEqual(1, len(followed_for_case))

    def test_follow_case_with_missing_case_id_should_return_400(self):
        response = self._subject.create('/api/v2/me/followed-cases', {})
        self.assertEqual(400, response.status_code)

    def test_follow_case_with_non_integer_case_id_should_return_400(self):
        response = self._subject.create('/api/v2/me/followed-cases', {'case_id': 'abc'})
        self.assertEqual(400, response.status_code)

    def test_follow_unknown_case_should_return_404(self):
        response = self._subject.create('/api/v2/me/followed-cases', {'case_id': 999_999_999})
        self.assertEqual(404, response.status_code)

    def test_unfollow_case_should_return_204_and_remove_from_list(self):
        case_id = self._subject.create_dummy_case()
        self._subject.create('/api/v2/me/followed-cases', {'case_id': case_id})

        response = self._subject.delete(f'/api/v2/me/followed-cases/{case_id}')
        self.assertEqual(204, response.status_code)

        listed = self._subject.get('/api/v2/me/followed-cases').json()
        self.assertNotIn(case_id, [c['case_id'] for c in listed])

    def test_unfollow_unfollowed_case_should_return_204(self):
        # Idempotent unfollow: the SPA's toggle should never error out
        # because a stale UI clicked the wrong direction.
        case_id = self._subject.create_dummy_case()
        response = self._subject.delete(f'/api/v2/me/followed-cases/{case_id}')
        self.assertEqual(204, response.status_code)

    def test_followers_endpoint_should_list_following_users(self):
        case_id = self._subject.create_dummy_case()
        self._subject.create('/api/v2/me/followed-cases', {'case_id': case_id})

        response = self._subject.get(f'/api/v2/cases/{case_id}/followers').json()
        # We expect at least the administrator (who follows via the
        # POST above) to show up.
        self.assertGreaterEqual(len(response), 1)
        for row in response:
            self.assertIn('user_id', row)
            self.assertIn('user_login', row)
            self.assertIn('user_name', row)

    def test_followers_for_unknown_case_should_return_404(self):
        response = self._subject.get('/api/v2/cases/999999999/followers')
        self.assertEqual(404, response.status_code)
