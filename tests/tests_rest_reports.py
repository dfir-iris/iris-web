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
        self.assertEqual(200, response.status_code, response.text)
        with BytesIO(response.content) as content:
            document = Document(content)
            self.assertEqual('IrisInitialClient (legacy::use client.customer_name)', document.paragraphs[0].text)

    def test_generate_docx_report_should_render_markdown_variable_case_description(self):
        data = {'report_name': 'name', 'report_type': 1, 'report_language': 1, 'report_description': 'description',
                'report_name_format': 'report_name_format'}
        report_identifier = self._subject.create_report(data, 'variable_case_description_markdown.docx')
        case_body = {
            'case_name': 'case name',
            'case_description': '# Heading\n\n- **bold item**\n- *italic item*\n- normal item\n\n'
                                '```python\n'
                                'print("hello")\n'
                                'for i in range(2):\n'
                                '    print(i)\n'
                                '```\n\n'
                                '|Table 1| Table 2 | Table 3 |\n'
                                '|--|--|--|\n'
                                '|  A  |  1  |  3  |\n'
                                '|  B  |  2  |  4  |\n'
                                '|Single column|\n'
                                '|--|\n'
                                '|Only value|\n'
                                '|C1|C2|C3|C4|C5|\n'
                                '|--|--|--|--|--|\n'
                                '|v1|v2|v3|v4|v5|',
            'case_customer_id': 1,
            'case_soc_id': ''
        }
        case_identifier = self._subject.create('/api/v2/cases', case_body).json()['case_id']

        response = self._subject.get(f'/case/report/generate-investigation/{report_identifier}',
                                     {'cid': case_identifier, 'safe': True})
        self.assertEqual(200, response.status_code, response.text)
        with BytesIO(response.content) as content:
            document = Document(content)
            full_text = '\n'.join(paragraph.text for paragraph in document.paragraphs)
            table_text = '\n'.join(
                cell.text
                for table in document.tables
                for row in table.rows
                for cell in row.cells
            )
            self.assertIn('Heading', full_text)
            heading_paragraphs = [p for p in document.paragraphs if p.text.strip() == 'Heading']
            self.assertTrue(heading_paragraphs, 'Heading paragraph missing')
            self.assertTrue(
                any('heading' in (p.style.name or '').lower() for p in heading_paragraphs),
                f'Heading paragraph style not applied: {[p.style.name for p in heading_paragraphs]}'
            )
            self.assertIn('bold item', full_text)
            self.assertIn('italic item', full_text)
            self.assertIn('normal item', full_text)
            self.assertIn('print("hello")', full_text)
            self.assertIn('for i in range(2):', full_text)
            self.assertIn('Table 1', table_text)
            self.assertIn('Table 2', table_text)
            self.assertIn('Table 3', table_text)
            self.assertIn('A', table_text)
            self.assertIn('B', table_text)
            self.assertIn('4', table_text)
            self.assertIn('Single column', table_text)
            self.assertIn('Only value', table_text)
            self.assertIn('C5', table_text)
            self.assertIn('v5', table_text)
            self.assertEqual(3, len(document.tables))
            self.assertEqual(3, len(document.tables[0].rows[0].cells))
            self.assertEqual(1, len(document.tables[1].rows[0].cells))
            self.assertEqual(5, len(document.tables[2].rows[0].cells))
            self.assertNotIn('**', full_text)
            self.assertNotIn('*italic item*', full_text)
            self.assertNotIn('```', full_text)
            self.assertNotIn('- ', full_text)

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

    def test_generate_md_report_should_render_ioc_comments(self):
        data = {'report_name': 'name', 'report_type': 1, 'report_language': 1, 'report_description': 'description',
                'report_name_format': 'report_name_format'}
        report_identifier = self._subject.create_report(data, 'variable_ioc_comments.md')
        case_identifier = self._subject.create_dummy_case()

        ioc_data = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': '', 'ioc_tags': ''}
        ioc_response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', ioc_data).json()
        ioc_identifier = ioc_response['ioc_id']
        comment_text = 'ioc comment for report export'
        self._subject.create(f'/api/v2/iocs/{ioc_identifier}/comments', {'comment_text': comment_text})

        response = self._subject.get(f'/case/report/generate-investigation/{report_identifier}',
                                     {'cid': case_identifier, 'safe': True})
        self.assertIn(comment_text, response.text)

    def test_generate_md_report_should_render_event_comments(self):
        data = {'report_name': 'name', 'report_type': 1, 'report_language': 1, 'report_description': 'description',
                'report_name_format': 'report_name_format'}
        report_identifier = self._subject.create_report(data, 'variable_event_comments.md')
        case_identifier = self._subject.create_dummy_case()

        event_data = {'event_title': 'title', 'event_category_id': 1,
                      'event_date': '2025-03-26T00:00:00.000', 'event_tz': '+00:00',
                      'event_assets': [], 'event_iocs': []}
        event_response = self._subject.create(f'/api/v2/cases/{case_identifier}/events', event_data).json()
        event_identifier = event_response['event_id']
        comment_text = 'event comment for report export'
        self._subject.create(f'/api/v2/events/{event_identifier}/comments', {'comment_text': comment_text})

        response = self._subject.get(f'/case/report/generate-investigation/{report_identifier}',
                                     {'cid': case_identifier, 'safe': True})
        self.assertIn(comment_text, response.text)

    def test_generate_md_report_should_render_note_comments(self):
        data = {'report_name': 'name', 'report_type': 1, 'report_language': 1, 'report_description': 'description',
                'report_name_format': 'report_name_format'}
        report_identifier = self._subject.create_report(data, 'variable_note_comments.md')
        case_identifier = self._subject.create_dummy_case()

        directory_response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                                  {'name': 'directory_name'}).json()
        directory_identifier = directory_response['id']
        note_response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes',
                                             {'directory_id': directory_identifier}).json()
        note_identifier = note_response['note_id']
        comment_text = 'note comment for report export'
        self._subject.create(f'/api/v2/notes/{note_identifier}/comments', {'comment_text': comment_text})

        response = self._subject.get(f'/case/report/generate-investigation/{report_identifier}',
                                     {'cid': case_identifier, 'safe': True})
        self.assertIn(comment_text, response.text)
