#  IRIS Source Code
#  Copyright (C) 2023 - DFIR-IRIS
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

_IDENTIFIER_FOR_NONEXISTENT_OBJECT = 123456789


class TestsRestNotes(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_create_note_should_return_201(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body)
        self.assertEqual(201, response.status_code)

    def test_create_note_should_accept_field_note_title_with_empty_value(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier, 'note_title': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        self.assertEqual('', response['note_title'])

    def test_create_note_should_accept_field_note_content_with_empty_value(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier, 'note_content': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        self.assertEqual('', response['note_content'])

    def test_create_note_in_sub_directory_should_return_directory_parent_id(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'parent_directory_name'}).json()
        parent_directory_identifier = response['id']
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name', 'parent_id': parent_directory_identifier}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier, 'note_content': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        self.assertEqual(parent_directory_identifier, response['directory']['parent_id'])

    def test_create_note_with_missing_case_identifier_should_return_404(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/notes', body)
        self.assertEqual(404, response.status_code)

    def test_create_note_with_missing_directory_should_return_400(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'directory_id': _IDENTIFIER_FOR_NONEXISTENT_OBJECT}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body)
        self.assertEqual(400, response.status_code)

    def test_create_note_with_directory_from_another_case_should_return_400(self):
        case_identifier = self._subject.create_dummy_case()
        case_identifier2 = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier2}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body)
        self.assertEqual(400, response.status_code)

    def test_create_note_should_return_object_with_field_modification_history(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        first_modification_history = next(iter(response['modification_history'].values()))
        self.assertEqual({'user': 'administrator', 'user_id': 1, 'action': 'created note'}, first_modification_history)

    def test_get_note_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        identifier = response['note_id']
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/notes/{identifier}')
        self.assertEqual(200, response.status_code)

    def test_get_note_should_return_404_when_note_does_not_exist(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/notes/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_get_note_should_return_404_when_case_does_not_exist(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        identifier = response['note_id']
        response = self._subject.get(f'/api/v2/cases/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/notes/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_update_note_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        identifier = response['note_id']
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/notes/{identifier}', {})
        self.assertEqual(200, response.status_code)

    def test_update_note_should_modify_note_title(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        identifier = response['note_id']
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/notes/{identifier}', {'note_title': 'title'}).json()
        self.assertEqual('title', response['note_title'])

    def test_update_note_should_return_400_when_requested_with_integer_note_title(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        identifier = response['note_id']
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/notes/{identifier}', {'note_title': 1})
        self.assertEqual(400, response.status_code)

    def test_update_note_should_return_400_when_requested_with_nonexistent_directory_id(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        identifier = response['note_id']
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/notes/{identifier}', {'directory_id': _IDENTIFIER_FOR_NONEXISTENT_OBJECT})
        self.assertEqual(400, response.status_code)

    def test_update_note_should_return_404_when_case_identifier_does_not_correspond_to_existing_case(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        identifier = response['note_id']
        response = self._subject.update(f'/api/v2/cases/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/notes/{identifier}', {})
        self.assertEqual(404, response.status_code)

    def test_update_note_should_return_404_when_identifier_does_not_correspond_to_existing_note(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.update(f'/api/v2/cases/{case_identifier}/notes/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}', {})
        self.assertEqual(404, response.status_code)

    def test_update_note_should_return_403_when_user_has_no_access_to_case(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        identifier = response['note_id']

        user = self._subject.create_dummy_user()
        response = user.update(f'/api/v2/cases/{case_identifier}/notes/{identifier}', {})
        self.assertEqual(403, response.status_code)

    def test_delete_note_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        identifier = response['note_id']
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}/notes/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_note_should_return_403_when_user_has_no_access_to_case(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        identifier = response['note_id']

        user = self._subject.create_dummy_user()
        response = user.delete(f'/api/v2/cases/{case_identifier}/notes/{identifier}')
        self.assertEqual(403, response.status_code)

    def test_delete_note_should_return_404_when_identifier_does_not_correspond_to_existing_note(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}/notes/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}')
        self.assertEqual(404, response.status_code)

    def test_delete_note_should_return_404_when_case_identifier_does_not_correspond_to_existing_note(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        identifier = response['note_id']
        response = self._subject.delete(f'/api/v2/cases/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/notes/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_get_note_should_return_404_when_note_is_deleted(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        identifier = response['note_id']
        self._subject.delete(f'/api/v2/cases/{case_identifier}/notes/{identifier}')
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/notes/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_socket_io_join_notes_overview_should_not_fail(self):
        case_identifier = self._subject.create_dummy_case()

        with self._subject.get_socket_io_client() as socket_io_client:
            socket_io_client.emit('join-notes-overview', f'case-{case_identifier}-notes')
            message = socket_io_client.receive()
            self.assertEqual('administrator', message['user'])
