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

    def test_generate_md_report_should_render_evidence_comments(self):
        data = {'report_name': 'name', 'report_type': 1, 'report_language': 1, 'report_description': 'description',
                'report_name_format': 'report_name_format'}
        report_identifier = self._subject.create_report(data, 'variable_evidence_comments.md')
        case_identifier = self._subject.create_dummy_case()

        evidence_response = self._subject.create(f'/api/v2/cases/{case_identifier}/evidences',
                                                 {'filename': 'filename'}).json()
        evidence_identifier = evidence_response['id']
        comment_text = 'evidence comment for report export'
        self._subject.create(f'/api/v2/evidences/{evidence_identifier}/comments', {'comment_text': comment_text})

        response = self._subject.get(f'/case/report/generate-investigation/{report_identifier}',
                                     {'cid': case_identifier, 'safe': True})
        self.assertIn(comment_text, response.text)
