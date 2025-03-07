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


class TestsRestEvidences(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_create_evidence_should_return_201(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'filename': 'filename'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/evidences', body)
        self.assertEqual(201, response.status_code)

    def test_create_evidence_should_return_400_when_field_filename_is_missing(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/evidences', {})
        self.assertEqual(400, response.status_code)

    def test_create_evidence_should_return_403_when_user_has_no_access_to_case(self):
        case_identifier = self._subject.create_dummy_case()

        user = self._subject.create_dummy_user()
        response = user.create(f'/api/v2/cases/{case_identifier}/evidences', {'filename': 'filename'})
        self.assertEqual(403, response.status_code)

    def test_create_evidence_should_return_404_when_case_is_missing(self):
        body = {'filename': 'filename'}
        response = self._subject.create(f'/api/v2/cases/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/evidences', body)
        self.assertEqual(404, response.status_code)

    def test_create_evidence_should_accept_field_type_id(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'filename': 'filename', 'type_id': 2}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/evidences', body).json()
        self.assertEqual(2, response['type_id'])

    def test_create_evidence_should_accept_field_file_hash(self):
        case_identifier = self._subject.create_dummy_case()
        file_hash = '88BC9EF6F07F0FAE922AB25EB226906542F8BA0DC1A221F3EA7273CBCB5DB0D4'
        body = {'filename': 'filename', 'file_hash': file_hash}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/evidences', body).json()
        self.assertEqual(file_hash, response['file_hash'])

    def test_create_evidence_should_accept_field_file_size(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'filename': 'filename', 'file_size': 77108}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/evidences', body).json()
        self.assertEqual(77108, response['file_size'])
