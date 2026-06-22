#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

import io
from unittest import TestCase
from iris import Iris

_IDENTIFIER_FOR_NONEXISTENT_OBJECT = 123456789


class TestsRestDatastore(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _get_root_folder_id(self, case_identifier):
        tree = self._subject.get(f'/api/v2/cases/{case_identifier}/datastore/tree').json()
        # Tree shape: {'d-<root_id>': {...}}
        root_key = next(iter(tree['data']))
        return int(root_key.split('-')[1])

    def _create_folder(self, case_identifier, name='Folder', parent=None):
        if parent is None:
            parent = self._get_root_folder_id(case_identifier)
        body = {'parent_node': parent, 'folder_name': name}
        return self._subject.create(f'/api/v2/cases/{case_identifier}/datastore/folders', body)

    def _upload_file(self, case_identifier, folder_id, filename='hello.txt', content=b'hello world',
                     description='desc'):
        data = {
            'file_original_name': filename,
            'file_description': description
        }
        files = {'file_content': (filename, io.BytesIO(content), 'application/octet-stream')}
        return self._subject.post_multipart_encoded_files(
            f'/api/v2/cases/{case_identifier}/datastore/folders/{folder_id}/files',
            data,
            files
        )

    # ------------------------------------------------------------------
    # tree
    # ------------------------------------------------------------------
    def test_get_tree_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/datastore/tree')
        self.assertEqual(200, response.status_code)

    def test_get_tree_should_return_404_when_case_does_not_exist(self):
        response = self._subject.get(f'/api/v2/cases/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/datastore/tree')
        self.assertEqual(404, response.status_code)

    def test_get_tree_should_return_403_when_user_has_no_access(self):
        case_identifier = self._subject.create_dummy_case()
        user = self._subject.create_dummy_user()
        response = user.get(f'/api/v2/cases/{case_identifier}/datastore/tree')
        self.assertEqual(403, response.status_code)

    def test_get_tree_should_include_root_directory(self):
        case_identifier = self._subject.create_dummy_case()
        tree = self._subject.get(f'/api/v2/cases/{case_identifier}/datastore/tree').json()['data']
        root_key = next(iter(tree))
        self.assertTrue(tree[root_key].get('is_root'))

    # ------------------------------------------------------------------
    # folder CRUD
    # ------------------------------------------------------------------
    def test_add_folder_should_return_201(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._create_folder(case_identifier, 'Folder1')
        self.assertEqual(201, response.status_code)

    def test_add_folder_should_return_400_when_missing_fields(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/datastore/folders', {})
        self.assertEqual(400, response.status_code)

    def test_add_folder_should_return_404_when_case_does_not_exist(self):
        response = self._subject.create(
            f'/api/v2/cases/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/datastore/folders',
            {'parent_node': 1, 'folder_name': 'X'}
        )
        self.assertEqual(404, response.status_code)

    def test_add_folder_should_return_403_when_user_has_no_access(self):
        case_identifier = self._subject.create_dummy_case()
        root = self._get_root_folder_id(case_identifier)
        user = self._subject.create_dummy_user()
        response = user.create(
            f'/api/v2/cases/{case_identifier}/datastore/folders',
            {'parent_node': root, 'folder_name': 'X'}
        )
        self.assertEqual(403, response.status_code)

    def test_rename_folder_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        created = self._create_folder(case_identifier, 'Folder1').json()['data']
        folder_id = created['path_id']
        response = self._subject.create(
            f'/api/v2/cases/{case_identifier}/datastore/folders/{folder_id}/rename',
            {'folder_name': 'Renamed'}
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual('Renamed', response.json()['data']['path_name'])

    def test_rename_folder_should_return_404_when_folder_missing(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(
            f'/api/v2/cases/{case_identifier}/datastore/folders/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/rename',
            {'folder_name': 'Renamed'}
        )
        self.assertEqual(404, response.status_code)

    def test_move_folder_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        root = self._get_root_folder_id(case_identifier)
        folder_a = self._create_folder(case_identifier, 'A', parent=root).json()['data']
        folder_b = self._create_folder(case_identifier, 'B', parent=root).json()['data']
        response = self._subject.create(
            f'/api/v2/cases/{case_identifier}/datastore/folders/{folder_a["path_id"]}/move',
            {'destination_node': folder_b['path_id']}
        )
        self.assertEqual(200, response.status_code)

    def test_move_folder_should_return_400_when_same_destination(self):
        case_identifier = self._subject.create_dummy_case()
        folder = self._create_folder(case_identifier, 'A').json()['data']
        response = self._subject.create(
            f'/api/v2/cases/{case_identifier}/datastore/folders/{folder["path_id"]}/move',
            {'destination_node': folder['path_id']}
        )
        self.assertEqual(400, response.status_code)

    def test_delete_folder_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        folder = self._create_folder(case_identifier, 'Folder1').json()['data']
        response = self._subject.delete(
            f'/api/v2/cases/{case_identifier}/datastore/folders/{folder["path_id"]}'
        )
        self.assertEqual(204, response.status_code)

    def test_delete_folder_should_return_404_when_folder_missing(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.delete(
            f'/api/v2/cases/{case_identifier}/datastore/folders/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}'
        )
        self.assertEqual(404, response.status_code)

    def test_delete_root_folder_should_return_400(self):
        case_identifier = self._subject.create_dummy_case()
        root = self._get_root_folder_id(case_identifier)
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}/datastore/folders/{root}')
        self.assertEqual(400, response.status_code)

    def test_list_folders_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/datastore/folders')
        self.assertEqual(200, response.status_code)

    def test_get_folder_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        folder = self._create_folder(case_identifier, 'Folder1').json()['data']
        response = self._subject.get(
            f'/api/v2/cases/{case_identifier}/datastore/folders/{folder["path_id"]}'
        )
        self.assertEqual(200, response.status_code)

    def test_get_folder_should_return_404_when_missing(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(
            f'/api/v2/cases/{case_identifier}/datastore/folders/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}'
        )
        self.assertEqual(404, response.status_code)

    # ------------------------------------------------------------------
    # file CRUD
    # ------------------------------------------------------------------
    def test_add_file_should_return_201(self):
        case_identifier = self._subject.create_dummy_case()
        root = self._get_root_folder_id(case_identifier)
        response = self._upload_file(case_identifier, root)
        self.assertEqual(201, response.status_code)

    def test_add_file_should_return_404_when_folder_missing(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._upload_file(case_identifier, _IDENTIFIER_FOR_NONEXISTENT_OBJECT)
        self.assertEqual(404, response.status_code)

    def test_add_file_should_return_404_when_case_missing(self):
        response = self._upload_file(_IDENTIFIER_FOR_NONEXISTENT_OBJECT, 1)
        self.assertEqual(404, response.status_code)

    def test_add_file_should_return_403_when_user_has_no_access(self):
        case_identifier = self._subject.create_dummy_case()
        root = self._get_root_folder_id(case_identifier)
        user = self._subject.create_dummy_user()
        files = {'file_content': ('hello.txt', io.BytesIO(b'hi'), 'application/octet-stream')}
        response = user.post_multipart_encoded_files(
            f'/api/v2/cases/{case_identifier}/datastore/folders/{root}/files',
            {'file_original_name': 'hello.txt'},
            files
        )
        self.assertEqual(403, response.status_code)

    def test_get_file_info_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        root = self._get_root_folder_id(case_identifier)
        created = self._upload_file(case_identifier, root).json()['data']
        response = self._subject.get(
            f'/api/v2/cases/{case_identifier}/datastore/files/{created["file_id"]}/info'
        )
        self.assertEqual(200, response.status_code)

    def test_get_file_info_should_return_404_when_missing(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(
            f'/api/v2/cases/{case_identifier}/datastore/files/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/info'
        )
        self.assertEqual(404, response.status_code)

    def test_view_file_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        root = self._get_root_folder_id(case_identifier)
        created = self._upload_file(case_identifier, root).json()['data']
        response = self._subject.get(
            f'/api/v2/cases/{case_identifier}/datastore/files/{created["file_id"]}'
        )
        self.assertEqual(200, response.status_code)

    def test_list_files_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/datastore/files')
        self.assertEqual(200, response.status_code)

    def test_list_files_should_return_total_zero_for_new_case(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/datastore/files').json()
        self.assertEqual(0, response['data']['total'])

    def test_list_files_should_return_400_when_order_by_invalid(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(
            f'/api/v2/cases/{case_identifier}/datastore/files',
            {'order_by': 'an_invalid_field'}
        )
        self.assertEqual(400, response.status_code)

    def test_list_files_should_return_uploaded_file(self):
        case_identifier = self._subject.create_dummy_case()
        root = self._get_root_folder_id(case_identifier)
        self._upload_file(case_identifier, root, filename='abc.txt')
        response = self._subject.get(f'/api/v2/cases/{case_identifier}/datastore/files').json()['data']
        self.assertEqual(1, response['total'])

    def test_update_file_should_change_description(self):
        case_identifier = self._subject.create_dummy_case()
        root = self._get_root_folder_id(case_identifier)
        created = self._upload_file(case_identifier, root).json()['data']
        data = {'file_description': 'updated'}
        response = self._subject.post_multipart_encoded_files(
            f'/api/v2/cases/{case_identifier}/datastore/files/{created["file_id"]}',
            data,
            {}
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual('updated', response.json()['data']['file_description'])

    def test_update_file_should_return_404_when_missing(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.post_multipart_encoded_files(
            f'/api/v2/cases/{case_identifier}/datastore/files/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}',
            {'file_description': 'x'},
            {}
        )
        self.assertEqual(404, response.status_code)

    def test_move_file_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        root = self._get_root_folder_id(case_identifier)
        folder = self._create_folder(case_identifier, 'Dest', parent=root).json()['data']
        created = self._upload_file(case_identifier, root).json()['data']
        response = self._subject.create(
            f'/api/v2/cases/{case_identifier}/datastore/files/{created["file_id"]}/move',
            {'destination_node': folder['path_id']}
        )
        self.assertEqual(200, response.status_code)

    def test_move_file_should_return_404_when_missing(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(
            f'/api/v2/cases/{case_identifier}/datastore/files/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/move',
            {'destination_node': 1}
        )
        self.assertEqual(404, response.status_code)

    def test_delete_file_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        root = self._get_root_folder_id(case_identifier)
        created = self._upload_file(case_identifier, root).json()['data']
        response = self._subject.delete(
            f'/api/v2/cases/{case_identifier}/datastore/files/{created["file_id"]}'
        )
        self.assertEqual(204, response.status_code)

    def test_delete_file_should_return_404_when_missing(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.delete(
            f'/api/v2/cases/{case_identifier}/datastore/files/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}'
        )
        self.assertEqual(404, response.status_code)

    def test_delete_file_should_return_403_when_user_has_no_access(self):
        case_identifier = self._subject.create_dummy_case()
        root = self._get_root_folder_id(case_identifier)
        created = self._upload_file(case_identifier, root).json()['data']
        user = self._subject.create_dummy_user()
        response = user.delete(
            f'/api/v2/cases/{case_identifier}/datastore/files/{created["file_id"]}'
        )
        self.assertEqual(403, response.status_code)
