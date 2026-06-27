#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""
Integration tests for `/api/v2/war-rooms`.

End-to-end hits against the docker-compose stack via the existing
`Iris` helper. Each test creates the dependencies it needs and the
`tearDown` clears every war room before the cases (the helper's
`clear_database` was extended to drop war rooms first so the FKs
unwind in the right order).
"""

from unittest import TestCase

from iris import Iris


class TestsRestWarRoomsCrud(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def _create(self, name='Crisis Alpha', **kwargs):
        body = {'name': name}
        body.update(kwargs)
        return self._subject.create('/api/v2/war-rooms', body)

    def test_create_should_return_201_and_the_war_room(self):
        response = self._create(description='Multi-case ransomware sweep')
        self.assertEqual(201, response.status_code)
        body = response.json()
        self.assertEqual('Crisis Alpha', body['name'])
        self.assertEqual('open', body['state'])
        self.assertIsNotNone(body['war_room_id'])
        self.assertIsNotNone(body['war_room_uuid'])

    def test_create_should_reject_empty_name(self):
        response = self._subject.create('/api/v2/war-rooms', {'name': '   '})
        self.assertEqual(400, response.status_code)

    def test_create_should_reject_invalid_color(self):
        response = self._create(color='blue')
        self.assertEqual(400, response.status_code)

    def test_create_should_accept_hex_color(self):
        response = self._create(color='#ff0044')
        self.assertEqual(201, response.status_code)
        self.assertEqual('#ff0044', response.json()['color'])

    def test_list_should_include_created_room(self):
        response = self._create(name='Listed Crisis')
        room_id = response.json()['war_room_id']
        listed = self._subject.get('/api/v2/war-rooms').json()
        ids = [r['war_room_id'] for r in listed]
        self.assertIn(room_id, ids)

    def test_list_should_filter_by_state(self):
        first = self._create(name='Open Room')
        second = self._create(name='Standby Room')
        room_id = second.json()['war_room_id']
        self._subject.patch(f'/api/v2/war-rooms/{room_id}', {'state': 'standby'})
        listed = self._subject.get('/api/v2/war-rooms',
                                    query_parameters={'state': 'standby'}).json()
        ids = [r['war_room_id'] for r in listed]
        self.assertIn(room_id, ids)
        self.assertNotIn(first.json()['war_room_id'], ids)

    def test_get_should_return_404_when_absent(self):
        response = self._subject.get('/api/v2/war-rooms/999999999')
        self.assertEqual(404, response.status_code)

    def test_patch_should_update_name(self):
        room_id = self._create().json()['war_room_id']
        response = self._subject.patch(f'/api/v2/war-rooms/{room_id}',
                                        {'name': 'Updated Name'})
        self.assertEqual(200, response.status_code)
        self.assertEqual('Updated Name', response.json()['name'])

    def test_patch_state_closed_should_stamp_closed_at(self):
        room_id = self._create().json()['war_room_id']
        response = self._subject.patch(f'/api/v2/war-rooms/{room_id}',
                                        {'state': 'closed'})
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual('closed', body['state'])
        self.assertIsNotNone(body['closed_at'])

    def test_patch_state_back_to_open_should_clear_closed_at(self):
        room_id = self._create().json()['war_room_id']
        self._subject.patch(f'/api/v2/war-rooms/{room_id}', {'state': 'closed'})
        response = self._subject.patch(f'/api/v2/war-rooms/{room_id}',
                                        {'state': 'open'})
        body = response.json()
        self.assertEqual('open', body['state'])
        self.assertIsNone(body['closed_at'])

    def test_delete_should_return_204(self):
        room_id = self._create().json()['war_room_id']
        response = self._subject.delete(f'/api/v2/war-rooms/{room_id}')
        self.assertEqual(204, response.status_code)


class TestsRestWarRoomsMembers(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_creator_should_be_lead_member(self):
        response = self._subject.create('/api/v2/war-rooms', {'name': 'A'})
        room_id = response.json()['war_room_id']
        members = self._subject.get(f'/api/v2/war-rooms/{room_id}/members').json()
        self.assertEqual(1, len(members))
        self.assertEqual('lead', members[0]['role'])


class TestsRestWarRoomsCaseAttachment(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_attach_case_should_return_201(self):
        room_id = self._subject.create('/api/v2/war-rooms',
                                        {'name': 'Attached'}).json()['war_room_id']
        case_id = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/war-rooms/{room_id}/cases',
                                         {'case_id': case_id, 'note': 'Primary'})
        self.assertEqual(201, response.status_code)
        body = response.json()
        self.assertEqual(case_id, body['case_id'])
        self.assertEqual('Primary', body['note'])

    def test_list_cases_should_include_attached_case(self):
        room_id = self._subject.create('/api/v2/war-rooms',
                                        {'name': 'Attached'}).json()['war_room_id']
        case_id = self._subject.create_dummy_case()
        self._subject.create(f'/api/v2/war-rooms/{room_id}/cases',
                              {'case_id': case_id})
        listed = self._subject.get(f'/api/v2/war-rooms/{room_id}/cases').json()
        case_ids = [c['case_id'] for c in listed]
        self.assertIn(case_id, case_ids)

    def test_attach_case_twice_should_be_idempotent(self):
        room_id = self._subject.create('/api/v2/war-rooms',
                                        {'name': 'Attached'}).json()['war_room_id']
        case_id = self._subject.create_dummy_case()
        first = self._subject.create(f'/api/v2/war-rooms/{room_id}/cases',
                                      {'case_id': case_id, 'note': 'first'})
        second = self._subject.create(f'/api/v2/war-rooms/{room_id}/cases',
                                       {'case_id': case_id, 'note': 'second'})
        self.assertEqual(201, first.status_code)
        # The second call must not raise on the unique constraint.
        self.assertEqual(201, second.status_code)
        listed = self._subject.get(f'/api/v2/war-rooms/{room_id}/cases').json()
        case_entries = [c for c in listed if c['case_id'] == case_id]
        self.assertEqual(1, len(case_entries))

    def test_detach_case_should_return_204(self):
        room_id = self._subject.create('/api/v2/war-rooms',
                                        {'name': 'Attached'}).json()['war_room_id']
        case_id = self._subject.create_dummy_case()
        self._subject.create(f'/api/v2/war-rooms/{room_id}/cases',
                              {'case_id': case_id})
        response = self._subject.delete(
            f'/api/v2/war-rooms/{room_id}/cases/{case_id}'
        )
        self.assertEqual(204, response.status_code)

    def test_case_war_rooms_endpoint_should_list_attachment(self):
        room_id = self._subject.create('/api/v2/war-rooms',
                                        {'name': 'Reverse Lookup'}).json()['war_room_id']
        case_id = self._subject.create_dummy_case()
        self._subject.create(f'/api/v2/war-rooms/{room_id}/cases',
                              {'case_id': case_id})
        listed = self._subject.get(f'/api/v2/cases/{case_id}/war-rooms').json()
        room_ids = [r['war_room_id'] for r in listed]
        self.assertIn(room_id, room_ids)
