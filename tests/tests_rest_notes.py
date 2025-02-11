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
        response = self._subject.create(f'/case/notes/directories/add',
                                        {'name': 'directory_name'}, query_parameters={'cid': case_identifier}).json()
        directory_identifier = response['data']['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body)
        self.assertEqual(201, response.status_code)

    def test_create_note_should_accept_field_note_title_with_empty_value(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/case/notes/directories/add',
                                        {'name': 'directory_name'}, query_parameters={'cid': case_identifier}).json()
        directory_identifier = response['data']['id']
        body = {'directory_id': directory_identifier, 'note_title': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        self.assertEqual('', response['note_title'])

    def test_create_note_should_accept_field_note_content_with_empty_value(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/case/notes/directories/add',
                                        {'name': 'directory_name'}, query_parameters={'cid': case_identifier}).json()
        directory_identifier = response['data']['id']
        body = {'directory_id': directory_identifier, 'note_content': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        self.assertEqual('', response['note_content'])

    def test_create_note_in_sub_directory_should_return_directory_parent_id(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/case/notes/directories/add',
                                        {'name': 'parent_directory_name'}, query_parameters={'cid': case_identifier}).json()
        parent_directory_identifier = response['data']['id']
        response = self._subject.create(f'/case/notes/directories/add',
                                        {'name': 'directory_name', 'parent_id': parent_directory_identifier},
                                        query_parameters={'cid': case_identifier}).json()
        directory_identifier = response['data']['id']
        body = {'directory_id': directory_identifier, 'note_content': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        self.assertEqual(parent_directory_identifier, response['directory']['parent_id'])

    def test_create_note_with_missing_case_identifier_should_return_404(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/case/notes/directories/add',
                                        {'name': 'directory_name'}, query_parameters={'cid': case_identifier}).json()
        directory_identifier = response['data']['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/notes', body)
        self.assertEqual(404, response.status_code)
