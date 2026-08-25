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
import json
import re
from iris import Iris


class Tests(TestCase):
    _subject = None
    _ioc_count = 0
    _user_count = 0

    @classmethod
    def setUpClass(cls) -> None:
        cls._subject = Iris()
        cls._subject.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._subject.stop()

    # Note: this method is necessary because the state of the database is not reset between each test
    #       and we want to work with distinct object in each test
    @classmethod
    def _generate_new_dummy_ioc_value(cls):
        cls._ioc_count += 1
        return f'IOC value #{cls._ioc_count}'

    # Note: this method is necessary because the state of the database is not reset between each test
    #       and we want to work with distinct object in each test
    @classmethod
    def _generate_new_dummy_user_name(cls):
        cls._user_count += 1
        return f'user{cls._user_count}'

    def test_create_asset_should_not_fail(self):
        response = self._subject.create_asset()
        self.assertEqual('success', response['status'])

    def test_get_api_version_should_not_fail(self):
        response = self._subject.get_api_version()
        self.assertEqual('success', response['status'])

    def test_create_case_should_add_a_new_case(self):
        response = self._subject.get_cases()
        initial_case_count = len(response['data'])
        self._subject.create_case()
        response = self._subject.get_cases()
        case_count = len(response['data'])
        self.assertEqual(initial_case_count + 1, case_count)

    def test_update_case_should_not_require_case_name_issue_358(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        response = self._subject.update_case(case_identifier, {'case_tags': 'test,example'})
        self.assertEqual('success', response['status'])

    def test_custom_attribute_tabs_have_unique_ids_across_cases(self):
        # Look up the 'case' attribute definition dynamically -- do not hardcode its id,
        # the seeded attribute_id ordering is an implementation detail, not a contract.
        attributes = self._subject._api.get('/manage/attributes/list')['data']
        case_attribute = next(a for a in attributes if a['attribute_for'] == 'case')

        schema = {
            'Investigation Metadata': {
                'MITRE ATT&CK Tactic': {'type': 'input_string', 'mandatory': False, 'value': ''},
            }
        }

        # Create the cases BEFORE (re-)applying the attribute definition. New cases are not seeded
        # with custom_attributes at creation time (that only happens via the "Add case" modal echoing
        # its pre-fetched defaults back in the payload) -- but updating the attribute definition runs
        # update_all_attributes(), which retroactively backfills every case whose custom_attributes is
        # still None. Creating first and updating second reliably exercises that backfill path.
        case_a = self._subject.create_case()
        case_b = self._subject.create_case()

        response = self._subject._api.post(
            f'/manage/attributes/update/{case_attribute["attribute_id"]}',
            {'attribute_content': json.dumps(schema), 'partial_overwrite': True, 'complete_overwrite': False}
        )
        self.assertEqual('success', response['status'])

        session = self._subject.get_authenticated_session()
        status_a, html_a = self._subject.get_html(session, f'/case/details/{case_a["case_id"]}', case_id=case_a['case_id'])
        status_b, html_b = self._subject.get_html(session, f'/case/details/{case_b["case_id"]}', case_id=case_b['case_id'])

        self.assertEqual(200, status_a)
        self.assertEqual(200, status_b)

        # "Info" must still be the default active tab in both renders.
        self.assertIn('class="nav-link active show" id="pills-home-tab-nobd"', html_a)
        self.assertIn('class="nav-link active show" id="pills-home-tab-nobd"', html_b)

        # The generated tab id for the custom attribute pane must differ between two
        # independently-rendered cases -- this is false on the unfixed code (both render
        # "1_investigation_metadata" verbatim) and true once page_uid is a real per-render value.
        id_pattern = re.compile(r'id="(\w*1_investigation_metadata)"')
        id_a = id_pattern.search(html_a)
        id_b = id_pattern.search(html_b)
        self.assertIsNotNone(id_a, 'Investigation Metadata tab pane not found in case A details HTML')
        self.assertIsNotNone(id_b, 'Investigation Metadata tab pane not found in case B details HTML')
        self.assertNotEqual(id_a.group(1), id_b.group(1))