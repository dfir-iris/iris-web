#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
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
from iris import ADMINISTRATOR_USER_IDENTIFIER
from iris import IRIS_PERMISSION_SERVER_ADMINISTRATOR
from iris import IRIS_PERMISSION_ALERTS_READ
from iris import IRIS_PERMISSION_ALERTS_WRITE
from iris import IRIS_CASE_ACCESS_LEVEL_READ_ONLY

_IDENTIFIER_FOR_NONEXISTENT_OBJECT = 123456789


class TestsRestComments(TestCase):

    def setUp(self) -> None:
        self._subject = Iris()

    def tearDown(self):
        self._subject.clear_database()

    def test_get_alerts_comments_should_return_200(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        response = self._subject.get(f'/api/v2/alerts/{object_identifier}/comments')
        self.assertEqual(200, response.status_code)

    def test_get_alerts_comments_should_return_404_when_alert_is_not_found(self):
        response = self._subject.get(f'/api/v2/alerts/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/comments')
        self.assertEqual(404, response.status_code)

    def test_get_alerts_comments_should_return_403_when_user_has_no_permission_to_read_alerts(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        user = self._subject.create_dummy_user()
        response = user.get(f'/api/v2/alerts/{object_identifier}/comments')
        self.assertEqual(403, response.status_code)

    def test_get_alerts_comments_should_return_404_when_user_has_no_access_to_alerts_customer(self):
        customer_identifier = self._subject.create_dummy_customer()
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': customer_identifier,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']

        group_identifier = self._subject.create_dummy_group([IRIS_PERMISSION_ALERTS_READ])
        user = self._subject.create_dummy_user()
        body = {'groups_membership': [group_identifier]}
        self._subject.create(f'/manage/users/{user.get_identifier()}/groups/update', body)
        response = user.get(f'/api/v2/alerts/{object_identifier}/comments')
        self.assertEqual(404, response.status_code)

    def test_get_alerts_comments_should_return_field_data(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        response = self._subject.get(f'/api/v2/alerts/{object_identifier}/comments').json()
        self.assertEqual([], response['data'])

    def test_get_alerts_comments_should_accept_parameter_per_page(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        self._subject.create(f'/alerts/{object_identifier}/comments/add', {'comment_text': 'comment1'})
        self._subject.create(f'/alerts/{object_identifier}/comments/add', {'comment_text': 'comment2'})
        response = self._subject.get(f'/api/v2/alerts/{object_identifier}/comments', {'per_page': 1}).json()
        self.assertEqual(1, len(response['data']))

    def test_get_assets_comments_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        object_identifier = response['asset_id']
        response = self._subject.get(f'/api/v2/assets/{object_identifier}/comments')
        self.assertEqual(200, response.status_code)

    def test_get_assets_comments_should_return_404_when_user_has_no_permission_to_access_case(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        object_identifier = response['asset_id']

        user = self._subject.create_dummy_user()
        response = user.get(f'/api/v2/assets/{object_identifier}/comments')
        self.assertEqual(404, response.status_code)

    def test_get_assets_comments_should_return_404_when_asset_is_not_found(self):
        response = self._subject.get(f'/api/v2/assets/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/comments')
        self.assertEqual(404, response.status_code)

    def test_get_evidences_comments_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'filename': 'filename'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/evidences', body).json()
        object_identifier = response['id']
        response = self._subject.get(f'/api/v2/evidences/{object_identifier}/comments')
        self.assertEqual(200, response.status_code)

    def test_get_iocs_comments_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        object_identifier = response['ioc_id']
        response = self._subject.get(f'/api/v2/iocs/{object_identifier}/comments')
        self.assertEqual(200, response.status_code)

    def test_get_notes_comments_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        object_identifier = response['note_id']
        response = self._subject.get(f'/api/v2/notes/{object_identifier}/comments')
        self.assertEqual(200, response.status_code)

    def test_get_tasks_comments_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'dummy title'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        object_identifier = response['id']
        response = self._subject.get(f'/api/v2/tasks/{object_identifier}/comments')
        self.assertEqual(200, response.status_code)

    def test_get_events_comments_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()

        body = {'event_title': 'title', 'event_category_id': 1,
                'event_date': '2025-03-26T00:00:00.000', 'event_tz': '+00:00',
                'event_assets': [], 'event_iocs': []}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/events', body).json()
        object_identifier = response['event_id']

        response = self._subject.get(f'/api/v2/events/{object_identifier}/comments')
        self.assertEqual(200, response.status_code)

    def test_create_alerts_comment_should_return_201(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        response = self._subject.create(f'/api/v2/alerts/{object_identifier}/comments', {})
        self.assertEqual(201, response.status_code)

    def test_create_alerts_comment_should_set_comment_text(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        body = {
            'comment_text': 'comment text'
        }
        response = self._subject.create(f'/api/v2/alerts/{object_identifier}/comments', body).json()
        self.assertEqual('comment text', response['comment_text'])

    def test_create_alerts_comment_should_set_comment_alert_id(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        response = self._subject.create(f'/api/v2/alerts/{object_identifier}/comments', {}).json()
        self.assertEqual(object_identifier, response['comment_alert_id'])

    def test_create_alerts_comment_should_set_comment_user_id(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        response = self._subject.create(f'/api/v2/alerts/{object_identifier}/comments', {}).json()
        self.assertEqual(ADMINISTRATOR_USER_IDENTIFIER, response['comment_user_id'])

    def test_create_alerts_comment_should_add_history_entry_on_alert(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        self._subject.create(f'/api/v2/alerts/{object_identifier}/comments', {}).json()
        response = self._subject.get(f'/api/v2/alerts/{object_identifier}', body).json()
        history_entry = self._subject.get_most_recent_object_history_entry(response)
        self.assertEqual('commented', history_entry['action'])

    def test_create_alerts_comment_should_call_module_hook(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']

        module_identifier = self._subject.get_module_identifier_by_name('IrisCheck')
        self._subject.create(f'/manage/modules/enable/{module_identifier}', {})
        self._subject.create(f'/api/v2/alerts/{object_identifier}/comments', {})
        self._subject.create(f'/manage/modules/disable/{module_identifier}', {})
        task = self._subject.wait_for_module_task()
        self.assertEqual('iris_check_module::on_postload_alert_commented', task['module'])

    def test_create_alerts_comment_should_be_tracked(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']

        self._subject.create(f'/api/v2/alerts/{object_identifier}/comments', {})
        activity = self._subject.get_latest_activity()
        self.assertEqual(f'Alert "{object_identifier}" commented', activity['activity_desc'])

    def test_create_alerts_comment_should_return_404_when_alert_is_not_found(self):
        response = self._subject.create(f'/api/v2/alerts/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/comments', {})
        self.assertEqual(404, response.status_code)

    def test_create_alerts_comment_should_return_400_when_comment_text_is_not_a_string(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        body = {
            'comment_text': 1
        }
        response = self._subject.create(f'/api/v2/alerts/{object_identifier}/comments', body)
        self.assertEqual(400, response.status_code)

    def test_create_assets_comments_should_return_201(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        object_identifier = response['asset_id']

        response = self._subject.create(f'/api/v2/assets/{object_identifier}/comments', {})
        self.assertEqual(201, response.status_code)

    def test_create_assets_comment_should_set_comment_text(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        object_identifier = response['asset_id']

        body = {
            'comment_text': 'comment text'
        }
        response = self._subject.create(f'/api/v2/assets/{object_identifier}/comments', body).json()
        self.assertEqual('comment text', response['comment_text'])

    def test_create_assets_comment_should_return_404_when_asset_is_not_found(self):
        response = self._subject.create(f'/api/v2/assets/{_IDENTIFIER_FOR_NONEXISTENT_OBJECT}/comments', {})
        self.assertEqual(404, response.status_code)

    def test_create_assets_comment_should_return_404_when_user_has_only_read_only_case_access(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        object_identifier = response['asset_id']

        user = self._subject.create_dummy_user()
        user_identifier = user.get_identifier()
        body = {
            'access_level': IRIS_CASE_ACCESS_LEVEL_READ_ONLY,
            'cases_list': [case_identifier]
        }
        self._subject.create(f'/manage/users/{user_identifier}/cases-access/update', body)
        response = user.create(f'/api/v2/assets/{object_identifier}/comments', body)
        self.assertEqual(404, response.status_code)

    def test_create_assets_comment_should_return_400_when_comment_text_is_not_a_string(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        object_identifier = response['asset_id']
        body = {
            'comment_text': 1
        }
        response = self._subject.create(f'/api/v2/assets/{object_identifier}/comments', body)
        self.assertEqual(400, response.status_code)

    def test_create_evidences_comment_should_return_201(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'filename': 'filename'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/evidences', body).json()
        object_identifier = response['id']

        response = self._subject.create(f'/api/v2/evidences/{object_identifier}/comments', {})
        self.assertEqual(201, response.status_code)

    def test_create_evidences_comment_should_return_404_when_user_has_only_read_only_case_access(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'filename': 'filename'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/evidences', body).json()
        object_identifier = response['id']

        user = self._subject.create_dummy_user()
        user_identifier = user.get_identifier()
        body = {
            'access_level': IRIS_CASE_ACCESS_LEVEL_READ_ONLY,
            'cases_list': [case_identifier]
        }
        self._subject.create(f'/manage/users/{user_identifier}/cases-access/update', body)
        response = user.create(f'/api/v2/evidences/{object_identifier}/comments', body)
        self.assertEqual(404, response.status_code)

    def test_create_iocs_comment_should_return_201(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        object_identifier = response['ioc_id']

        response = self._subject.create(f'/api/v2/iocs/{object_identifier}/comments', {})
        self.assertEqual(201, response.status_code)

    def test_create_notes_comment_should_return_201(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        object_identifier = response['note_id']

        response = self._subject.create(f'/api/v2/notes/{object_identifier}/comments', {})
        self.assertEqual(201, response.status_code)

    def test_delete_case_with_ioc_comment_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        object_identifier = response['ioc_id']

        self._subject.create(f'/api/v2/iocs/{object_identifier}/comments', {})
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_case_with_ioc_comment_should_not_delete_comments_in_another_case(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        object_identifier = response['ioc_id']
        self._subject.create(f'/api/v2/iocs/{object_identifier}/comments', {})

        case_identifier2 = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier2}/iocs', body).json()
        object_identifier2 = response['ioc_id']
        self._subject.create(f'/api/v2/iocs/{object_identifier2}/comments', {})
        self._subject.delete(f'/api/v2/cases/{case_identifier2}')

        response = self._subject.get(f'/api/v2/iocs/{object_identifier}/comments').json()
        self.assertEqual(1, response['total'])

    def test_delete_case_with_asset_comment_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        object_identifier = response['asset_id']

        self._subject.create(f'/api/v2/assets/{object_identifier}/comments', {})
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_case_with_evidences_comment_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'filename': 'filename'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/evidences', body).json()
        object_identifier = response['id']

        self._subject.create(f'/api/v2/evidences/{object_identifier}/comments', {})
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_case_with_notes_comment_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        object_identifier = response['note_id']

        self._subject.create(f'/api/v2/notes/{object_identifier}/comments', {})
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}')
        self.assertEqual(204, response.status_code)

    def test_create_tasks_comment_should_return_201(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'dummy title'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        object_identifier = response['id']

        response = self._subject.create(f'/api/v2/tasks/{object_identifier}/comments', {})
        self.assertEqual(201, response.status_code)

    def test_delete_case_with_tasks_comment_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'dummy title'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        object_identifier = response['id']

        self._subject.create(f'/api/v2/tasks/{object_identifier}/comments', {})
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}')
        self.assertEqual(204, response.status_code)

    def test_create_events_comment_should_return_201(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'event_title': 'title', 'event_category_id': 1,
                'event_date': '2025-03-26T00:00:00.000', 'event_tz': '+00:00',
                'event_assets': [], 'event_iocs': []}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/events', body).json()
        object_identifier = response['event_id']

        response = self._subject.create(f'/api/v2/events/{object_identifier}/comments', {})
        self.assertEqual(201, response.status_code)

    def test_delete_case_with_events_comment_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'event_title': 'title', 'event_category_id': 1,
                'event_date': '2025-03-26T00:00:00.000', 'event_tz': '+00:00',
                'event_assets': [], 'event_iocs': []}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/events', body).json()
        object_identifier = response['event_id']

        self._subject.create(f'/api/v2/events/{object_identifier}/comments', {})
        response = self._subject.delete(f'/api/v2/cases/{case_identifier}')
        self.assertEqual(204, response.status_code)

    def test_get_alerts_comment_should_return_200(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        response = self._subject.create(f'/api/v2/alerts/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.get(f'/api/v2/alerts/{object_identifier}/comments/{identifier}', {})
        self.assertEqual(200, response.status_code)

    def test_get_assets_comment_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        object_identifier = response['asset_id']
        response = self._subject.create(f'/api/v2/assets/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']

        response = self._subject.get(f'/api/v2/assets/{object_identifier}/comments/{identifier}', {})
        self.assertEqual(200, response.status_code)

    def test_get_evidences_comment_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'filename': 'filename'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/evidences', body).json()
        object_identifier = response['id']
        response = self._subject.create(f'/api/v2/evidences/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.get(f'/api/v2/evidences/{object_identifier}/comments/{identifier}', {})
        self.assertEqual(200, response.status_code)

    def test_get_iocs_comment_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        object_identifier = response['ioc_id']
        response = self._subject.create(f'/api/v2/iocs/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.get(f'/api/v2/iocs/{object_identifier}/comments/{identifier}', {})
        self.assertEqual(200, response.status_code)

    def test_get_notes_comments_should_return_200_when_there_is_a_comment(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        object_identifier = response['note_id']
        response = self._subject.create(f'/api/v2/notes/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.get(f'/api/v2/notes/{object_identifier}/comments/{identifier}', {})
        self.assertEqual(200, response.status_code)

    def test_get_tasks_comment_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'dummy title'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        object_identifier = response['id']
        response = self._subject.create(f'/api/v2/tasks/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.get(f'/api/v2/tasks/{object_identifier}/comments/{identifier}', {})
        self.assertEqual(200, response.status_code)

    def test_get_events_comment_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'event_title': 'title', 'event_category_id': 1,
                'event_date': '2025-03-26T00:00:00.000', 'event_tz': '+00:00',
                'event_assets': [], 'event_iocs': []}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/events', body).json()
        object_identifier = response['event_id']
        response = self._subject.create(f'/api/v2/events/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.get(f'/api/v2/events/{object_identifier}/comments/{identifier}', {})
        self.assertEqual(200, response.status_code)

    def test_update_alerts_comment_should_return_200(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        response = self._subject.create(f'/api/v2/alerts/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']

        body = {'comment_text': 'comment'}
        response = self._subject.update(f'/api/v2/alerts/{object_identifier}/comments/{identifier}', body)
        self.assertEqual(200, response.status_code)

    def test_update_assets_comment_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        object_identifier = response['asset_id']
        response = self._subject.create(f'/api/v2/assets/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']

        body = {'comment_text': 'comment'}
        response = self._subject.update(f'/api/v2/assets/{object_identifier}/comments/{identifier}', body)
        self.assertEqual(200, response.status_code)

    def test_update_evidences_comment_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'filename': 'filename'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/evidences', body).json()
        object_identifier = response['id']
        response = self._subject.create(f'/api/v2/evidences/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.update(f'/api/v2/evidences/{object_identifier}/comments/{identifier}', {})
        self.assertEqual(200, response.status_code)

    def test_update_iocs_comment_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        object_identifier = response['ioc_id']
        response = self._subject.create(f'/api/v2/iocs/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.update(f'/api/v2/iocs/{object_identifier}/comments/{identifier}', {})
        self.assertEqual(200, response.status_code)

    def test_update_notes_comment_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        object_identifier = response['note_id']
        response = self._subject.create(f'/api/v2/notes/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.update(f'/api/v2/notes/{object_identifier}/comments/{identifier}', {})
        self.assertEqual(200, response.status_code)

    def test_update_tasks_comment_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'dummy title'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        object_identifier = response['id']
        response = self._subject.create(f'/api/v2/tasks/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.update(f'/api/v2/tasks/{object_identifier}/comments/{identifier}', {})
        self.assertEqual(200, response.status_code)

    def test_update_events_comment_should_return_200(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'event_title': 'title', 'event_category_id': 1,
                'event_date': '2025-03-26T00:00:00.000', 'event_tz': '+00:00',
                'event_assets': [], 'event_iocs': []}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/events', body).json()
        object_identifier = response['event_id']
        response = self._subject.create(f'/api/v2/events/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.update(f'/api/v2/events/{object_identifier}/comments/{identifier}', {})
        self.assertEqual(200, response.status_code)

    def test_delete_alerts_comment_should_return_204(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        response = self._subject.create(f'/api/v2/alerts/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.delete(f'/api/v2/alerts/{object_identifier}/comments/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_get_alerts_comment_should_return_404_when_deleted(self):
        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = self._subject.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        response = self._subject.create(f'/api/v2/alerts/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        self._subject.delete(f'/api/v2/alerts/{object_identifier}/comments/{identifier}')
        response = self._subject.get(f'/api/v2/alerts/{object_identifier}/comments/{identifier}')
        self.assertEqual(404, response.status_code)

    def test_delete_alerts_comment_should_return_403_when_comment_was_created_by_another_user(self):
        user = self._subject.create_dummy_user([IRIS_PERMISSION_SERVER_ADMINISTRATOR, IRIS_PERMISSION_ALERTS_WRITE])

        body = {
            'alert_title': 'title',
            'alert_severity_id': 4,
            'alert_status_id': 3,
            'alert_customer_id': 1,
        }
        response = user.create('/api/v2/alerts', body).json()
        object_identifier = response['alert_id']
        response = user.create(f'/api/v2/alerts/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.delete(f'/api/v2/alerts/{object_identifier}/comments/{identifier}')
        self.assertEqual(403, response.status_code)

    def test_delete_assets_comment_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'asset_type_id': 1, 'asset_name': 'admin_laptop_test'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/assets', body).json()
        object_identifier = response['asset_id']

        response = self._subject.create(f'/api/v2/assets/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.delete(f'/api/v2/assets/{object_identifier}/comments/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_evidences_comment_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'filename': 'filename'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/evidences', body).json()
        object_identifier = response['id']

        response = self._subject.create(f'/api/v2/evidences/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']
        response = self._subject.delete(f'/api/v2/evidences/{object_identifier}/comments/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_iocs_comment_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'ioc_type_id': 1, 'ioc_tlp_id': 2, 'ioc_value': '8.8.8.8', 'ioc_description': 'rewrw', 'ioc_tags': ''}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/iocs', body).json()
        object_identifier = response['ioc_id']
        response = self._subject.create(f'/api/v2/iocs/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']

        response = self._subject.delete(f'/api/v2/iocs/{object_identifier}/comments/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_notes_comment_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes-directories',
                                        {'name': 'directory_name'}).json()
        directory_identifier = response['id']
        body = {'directory_id': directory_identifier}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/notes', body).json()
        object_identifier = response['note_id']
        response = self._subject.create(f'/api/v2/notes/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']

        response = self._subject.delete(f'/api/v2/notes/{object_identifier}/comments/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_tasks_comment_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'task_assignees_id': [], 'task_status_id': 1, 'task_title': 'dummy title'}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/tasks', body).json()
        object_identifier = response['id']
        response = self._subject.create(f'/api/v2/tasks/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']

        response = self._subject.delete(f'/api/v2/tasks/{object_identifier}/comments/{identifier}')
        self.assertEqual(204, response.status_code)

    def test_delete_events_comment_should_return_204(self):
        case_identifier = self._subject.create_dummy_case()
        body = {'event_title': 'title', 'event_category_id': 1,
                'event_date': '2025-03-26T00:00:00.000', 'event_tz': '+00:00',
                'event_assets': [], 'event_iocs': []}
        response = self._subject.create(f'/api/v2/cases/{case_identifier}/events', body).json()
        object_identifier = response['event_id']
        response = self._subject.create(f'/api/v2/events/{object_identifier}/comments', {}).json()
        identifier = response['comment_id']

        response = self._subject.delete(f'/api/v2/events/{object_identifier}/comments/{identifier}')
        self.assertEqual(204, response.status_code)
