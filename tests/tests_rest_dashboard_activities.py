#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
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


class TestsRestDashboardActivities(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_list_recent_activities_should_return_200(self):
        response = self._subject.get('/api/v2/dashboard/activities/recent')
        self.assertEqual(200, response.status_code)

    def test_list_recent_activities_should_return_a_list(self):
        response = self._subject.get('/api/v2/dashboard/activities/recent').json()
        self.assertIsInstance(response, list)

    def test_list_recent_activities_should_include_recently_created_case(self):
        self._subject.create_dummy_case()
        response = self._subject.get('/api/v2/dashboard/activities/recent').json()
        self.assertGreaterEqual(len(response), 1)

    def test_list_recent_activities_entries_should_include_user_name(self):
        self._subject.create_dummy_case()
        response = self._subject.get('/api/v2/dashboard/activities/recent').json()
        self.assertIn('user_name', response[0])

    def test_list_recent_activities_entries_should_include_activity_date(self):
        self._subject.create_dummy_case()
        response = self._subject.get('/api/v2/dashboard/activities/recent').json()
        self.assertIn('activity_date', response[0])

    def test_list_recent_activities_entries_should_include_activity_description(self):
        self._subject.create_dummy_case()
        response = self._subject.get('/api/v2/dashboard/activities/recent').json()
        self.assertIn('activity_desc', response[0])

    def test_list_recent_activities_should_honour_limit_query_param(self):
        # Create a few cases so we have multiple activity entries.
        for _ in range(3):
            self._subject.create_dummy_case()
        response = self._subject.get('/api/v2/dashboard/activities/recent?limit=1').json()
        self.assertEqual(1, len(response))

    def test_list_recent_activities_should_clamp_invalid_limit(self):
        # Negative / zero limits should fall back to the default rather than
        # erroring out.
        response = self._subject.get('/api/v2/dashboard/activities/recent?limit=-5')
        self.assertEqual(200, response.status_code)

    def test_list_recent_activities_should_honour_offset_query_param(self):
        # Two pages of size 1 — the first row of page 2 must differ from
        # the first row of page 1 (assuming we have at least 2 activity
        # entries, which any populated case will provide).
        for _ in range(3):
            self._subject.create_dummy_case()
        first_page = self._subject.get('/api/v2/dashboard/activities/recent?limit=1&offset=0').json()
        second_page = self._subject.get('/api/v2/dashboard/activities/recent?limit=1&offset=1').json()
        self.assertEqual(1, len(first_page))
        self.assertEqual(1, len(second_page))
        if first_page and second_page:
            # IDs are stable per-row, so two distinct offsets must yield
            # two distinct rows.
            self.assertNotEqual(first_page[0].get('id'), second_page[0].get('id'))

    def test_list_recent_activities_should_scope_to_user_accessible_cases(self):
        # An activity authored on a case the other user has no access to
        # must not leak into their feed.
        case_identifier = self._subject.create_dummy_case()
        # Make sure the case exists (the call itself creates an activity row).
        self.assertIsNotNone(case_identifier)

        other_user = self._subject.create_dummy_user()
        response = other_user.get('/api/v2/dashboard/activities/recent').json()
        # The other user has no access to the case we created — none of the
        # returned rows should reference it.
        self.assertTrue(all(row.get('case_id') != case_identifier for row in response))

    def test_list_recent_major_case_activities_should_return_200(self):
        response = self._subject.get('/api/v2/dashboard/activities/cases/major')
        self.assertEqual(200, response.status_code)

    def test_list_recent_major_case_activities_should_include_required_fields(self):
        self._subject.create_dummy_case()
        response = self._subject.get('/api/v2/dashboard/activities/cases/major').json()

        self.assertGreaterEqual(len(response), 1)
        self.assertIn('case_id', response[0])
        self.assertIn('case_name', response[0])
        self.assertIn('owner_name', response[0])
        self.assertIn('opened_by_name', response[0])
        self.assertIn('customer_name', response[0])

    def test_list_recent_major_case_activities_should_honour_limit_offset(self):
        for _ in range(3):
            self._subject.create_dummy_case()

        first_page = self._subject.get('/api/v2/dashboard/activities/cases/major?limit=1&offset=0').json()
        second_page = self._subject.get('/api/v2/dashboard/activities/cases/major?limit=1&offset=1').json()

        self.assertEqual(1, len(first_page))
        self.assertEqual(1, len(second_page))
        if first_page and second_page:
            self.assertNotEqual(first_page[0].get('id'), second_page[0].get('id'))
