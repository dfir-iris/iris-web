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
from io import BytesIO
from docx import Document

from iris import Iris


class TestsRestReports(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()
        response = self._subject.get('/manage/templates/list').json()
        for report_template in response['data']:
            identifier = report_template['id']
            self._subject.create(f'/manage/templates/delete/{identifier}', {})

    def test_generate_docx_report__in_safe_mode_should_return_200(self):
        data = {'report_name': 'name', 'report_type': 1, 'report_language': 1, 'report_description': 'description',
                'report_name_format': 'report_name_format'}
        report_identifier = self._subject.create_report(data, 'empty.docx')
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/case/report/generate-investigation/{report_identifier}',
                                     {'cid': case_identifier, 'safe': True})
        self.assertEqual(200, response.status_code)

    def test_generate_docx_report_should_render_variable_case_for_customer(self):
        data = {'report_name': 'name', 'report_type': 1, 'report_language': 1, 'report_description': 'description',
                'report_name_format': 'report_name_format'}
        report_identifier = self._subject.create_report(data, 'variable_case_for_customer.docx')
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/case/report/generate-investigation/{report_identifier}',
                                     {'cid': case_identifier, 'safe': True})
        with BytesIO(response.content) as content:
            document = Document(content)
            self.assertEqual('IrisInitialClient (legacy::use client.customer_name)', document.paragraphs[0].text)

    def test_generate_md_report_should_render_variable_case_name(self):
        data = {'report_name': 'name', 'report_type': 1, 'report_language': 1, 'report_description': 'description',
                'report_name_format': 'report_name_format'}
        report_identifier = self._subject.create_report(data, 'variable_case_name.md')
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/case/report/generate-investigation/{report_identifier}',
                                     {'cid': case_identifier, 'safe': True})
        self.assertEqual(f'#{case_identifier} - case name', response.text)

    def test_generate_md_report_should_render_variable_case_for_customer(self):
        data = {'report_name': 'name', 'report_type': 1, 'report_language': 1, 'report_description': 'description',
                'report_name_format': 'report_name_format'}
        report_identifier = self._subject.create_report(data, 'variable_case_for_customer.md')
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/case/report/generate-investigation/{report_identifier}',
                                     {'cid': case_identifier, 'safe': True})
        self.assertEqual('IrisInitialClient (legacy::use client.customer_name)', response.text)

    def test_generate_md_activities_report_should_render_variable_case_for_customer_when(self):
        data = {'report_name': 'name', 'report_type': 2, 'report_language': 1, 'report_description': 'description',
                'report_name_format': 'report_name_format'}
        report_identifier = self._subject.create_report(data, 'variable_case_for_customer.md')
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.get(f'/case/report/generate-activities/{report_identifier}',
                                     {'cid': case_identifier, 'safe': True})
        self.assertEqual('IrisInitialClient (legacy::use client.customer_name)', response.text)

    def test_generate_md_report_should_render_task_comments(self):
        data = {'report_name': 'name', 'report_type': 1, 'report_language': 1, 'report_description': 'description',
                'report_name_format': 'report_name_format'}
        report_identifier = self._subject.create_report(data, 'variable_task_comments.md')
        case_identifier = self._subject.create_dummy_case()

        task_data = {'task_assignees_id': [], 'task_description': '', 'task_status_id': 1, 'task_tags': '',
                     'task_title': 'dummy title', 'custom_attributes': {}}
        task_response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', task_data).json()
        task_identifier = task_response['id']
        comment_text = 'task comment for report export'
        self._subject.create(f'/api/v2/tasks/{task_identifier}/comments', {'comment_text': comment_text})

        response = self._subject.get(f'/case/report/generate-investigation/{report_identifier}',
                                     {'cid': case_identifier, 'safe': True})
        self.assertIn(comment_text, response.text)

    def test_generate_md_report_should_render_asset_comments(self):
        data = {'report_name': 'name', 'report_type': 1, 'report_language': 1, 'report_description': 'description',
                'report_name_format': 'report_name_format'}
        report_identifier = self._subject.create_report(data, 'variable_asset_comments.md')
        case_identifier = self._subject.create_dummy_case()

        asset_data = {'asset_type_id': 1, 'asset_name': 'asset with comments'}
        asset_response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', asset_data).json()
        asset_identifier = asset_response['asset_id']
        comment_text = 'asset comment for report export'
        self._subject.create(f'/api/v2/assets/{asset_identifier}/comments', {'comment_text': comment_text})

        response = self._subject.get(f'/case/report/generate-investigation/{report_identifier}',
                                     {'cid': case_identifier, 'safe': True})
        self.assertIn(comment_text, response.text)
