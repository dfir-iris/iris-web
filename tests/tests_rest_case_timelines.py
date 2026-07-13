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
Integration tests for `/api/v2/cases/<id>/timelines`.

Covers the create-case → auto-Main flow, full CRUD on user-created
timelines, and the m2m wiring between events and timelines via the
events endpoint's `timeline_ids` field. Hits the docker-compose stack
end-to-end through the existing `Iris` helper.
"""

from unittest import TestCase

from iris import Iris


class TestsRestCaseTimelines(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_new_case_should_have_a_default_main_timeline(self):
        case_id = self._subject.create_dummy_case()
        timelines = self._subject.get(f'/api/v2/cases/{case_id}/timelines').json()

        defaults = [t for t in timelines if t['is_default']]
        self.assertEqual(1, len(defaults))
        self.assertEqual('Main', defaults[0]['name'])

    def test_create_timeline_should_return_201_and_appear_in_list(self):
        case_id = self._subject.create_dummy_case()
        response = self._subject.create(
            f'/api/v2/cases/{case_id}/timelines',
            {'name': 'Attacker activity', 'color': '#ff0000'}
        )
        self.assertEqual(201, response.status_code)

        timelines = self._subject.get(f'/api/v2/cases/{case_id}/timelines').json()
        names = [t['name'] for t in timelines]
        self.assertIn('Attacker activity', names)

    def test_create_timeline_with_duplicate_name_should_return_400(self):
        case_id = self._subject.create_dummy_case()
        first = self._subject.create(
            f'/api/v2/cases/{case_id}/timelines', {'name': 'Network'}
        )
        self.assertEqual(201, first.status_code)
        second = self._subject.create(
            f'/api/v2/cases/{case_id}/timelines', {'name': 'Network'}
        )
        self.assertEqual(400, second.status_code)

    def test_create_timeline_with_invalid_color_should_return_400(self):
        case_id = self._subject.create_dummy_case()
        response = self._subject.create(
            f'/api/v2/cases/{case_id}/timelines',
            {'name': 'Bad', 'color': 'red'}
        )
        self.assertEqual(400, response.status_code)

    def test_create_timeline_with_empty_name_should_return_400(self):
        case_id = self._subject.create_dummy_case()
        response = self._subject.create(
            f'/api/v2/cases/{case_id}/timelines', {'name': '   '}
        )
        self.assertEqual(400, response.status_code)

    def test_update_timeline_should_change_fields(self):
        case_id = self._subject.create_dummy_case()
        created = self._subject.create(
            f'/api/v2/cases/{case_id}/timelines', {'name': 'Network'}
        ).json()

        updated = self._subject.update(
            f'/api/v2/cases/{case_id}/timelines/{created["timeline_id"]}',
            {'name': 'Network forensic', 'color': '#00aa55'}
        ).json()
        self.assertEqual('Network forensic', updated['name'])
        self.assertEqual('#00aa55', updated['color'])

    def test_delete_default_timeline_should_return_400(self):
        case_id = self._subject.create_dummy_case()
        timelines = self._subject.get(f'/api/v2/cases/{case_id}/timelines').json()
        default = next(t for t in timelines if t['is_default'])

        response = self._subject.delete(
            f'/api/v2/cases/{case_id}/timelines/{default["timeline_id"]}'
        )
        self.assertEqual(400, response.status_code)

    def test_delete_custom_timeline_should_return_204(self):
        case_id = self._subject.create_dummy_case()
        created = self._subject.create(
            f'/api/v2/cases/{case_id}/timelines', {'name': 'Throwaway'}
        ).json()
        response = self._subject.delete(
            f'/api/v2/cases/{case_id}/timelines/{created["timeline_id"]}'
        )
        self.assertEqual(204, response.status_code)

    def test_event_create_without_timeline_ids_should_attach_to_default(self):
        case_id = self._subject.create_dummy_case()
        event = self._subject.create(
            f'/api/v2/cases/{case_id}/events',
            {
                'event_title': 'Initial access',
                'event_content': '',
                'event_raw': '',
                'event_source': '',
                'event_date': '2026-01-01T00:00:00.000',
                'event_tz': '+00:00',
                'event_category_id': 1,
                'event_assets': [],
                'event_iocs': [],
                'event_in_summary': False,
                'event_in_graph': False
            }
        ).json()

        # Returned payload should expose the timeline_ids list and it
        # should include the Main default's id.
        self.assertIn('timeline_ids', event)
        self.assertEqual(1, len(event['timeline_ids']))

    def test_event_create_with_unknown_timeline_id_should_return_400(self):
        case_id = self._subject.create_dummy_case()
        response = self._subject.create(
            f'/api/v2/cases/{case_id}/events',
            {
                'event_title': 'Bad',
                'event_content': '',
                'event_raw': '',
                'event_source': '',
                'event_date': '2026-01-01T00:00:00.000',
                'event_tz': '+00:00',
                'event_category_id': 1,
                'event_assets': [],
                'event_iocs': [],
                'event_in_summary': False,
                'event_in_graph': False,
                'timeline_ids': [9999999]
            }
        )
        self.assertEqual(400, response.status_code)

    def test_event_update_can_move_event_between_timelines(self):
        case_id = self._subject.create_dummy_case()
        extra = self._subject.create(
            f'/api/v2/cases/{case_id}/timelines', {'name': 'Forensic'}
        ).json()

        event = self._subject.create(
            f'/api/v2/cases/{case_id}/events',
            {
                'event_title': 'Move me',
                'event_content': '',
                'event_raw': '',
                'event_source': '',
                'event_date': '2026-01-01T00:00:00.000',
                'event_tz': '+00:00',
                'event_category_id': 1,
                'event_assets': [],
                'event_iocs': [],
                'event_in_summary': False,
                'event_in_graph': False
            }
        ).json()

        updated = self._subject.update(
            f'/api/v2/cases/{case_id}/events/{event["event_id"]}',
            {
                'event_title': 'Move me',
                'event_content': '',
                'event_raw': '',
                'event_source': '',
                'event_date': '2026-01-01T00:00:00.000',
                'event_tz': '+00:00',
                'event_category_id': 1,
                'event_assets': [],
                'event_iocs': [],
                'event_in_summary': False,
                'event_in_graph': False,
                'timeline_ids': [extra['timeline_id']]
            }
        ).json()

        self.assertEqual([extra['timeline_id']], updated['timeline_ids'])
