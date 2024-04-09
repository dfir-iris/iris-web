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
from iris import API_URL
from graphql_api import GraphQLApi
from base64 import b64encode


class Tests(TestCase):

    _subject = None
    _ioc_count = 0

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

    def test_graphql_endpoint_should_reject_requests_with_wrong_authentication_token(self):
        graphql_api = GraphQLApi(API_URL + '/graphql', 64*'0')
        payload = {
            'query': '{ cases { name } }'
        }
        response = graphql_api.execute(payload)
        self.assertEqual(401, response.status_code)

    def test_graphql_cases_should_contain_the_initial_case(self):
        payload = {
            'query': '{ cases { name } }'
        }
        body = self._subject.execute_graphql_query(payload)
        case_names = []
        for case in body['data']['cases']:
            case_names.append(case['name'])
        self.assertIn('#1 - Initial Demo', case_names)

    def _get_first_case(self, body):
        for case in body['data']['cases']:
            if case['name'] == '#1 - Initial Demo':
                return case

    def test_graphql_cases_should_have_a_global_identifier(self):
        payload = {
            'query': '{ cases { id name } }'
        }
        body = self._subject.execute_graphql_query(payload)
        first_case = self._get_first_case(body)
        self.assertEqual(b64encode(b'CaseObject:1').decode(), first_case['id'])

    def test_graphql_create_ioc_should_not_fail(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                           ioc {{ iocValue }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertNotIn('errors', response)

    def test_graphql_delete_ioc_should_not_fail(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                 ioc {{ iocId }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        ioc_identifier = response['data']['iocCreate']['ioc']['iocId']
        payload = {
            'query': f'''mutation {{
                             iocDelete(iocId: {ioc_identifier} caseId: {case_identifier}) {{
                                 message
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(f'IOC {ioc_identifier} deleted', response['data']['iocDelete']['message'])

    def test_graphql_create_ioc_should_allow_optional_description_to_be_set(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        description = 'some description'
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}",
                                       description: "{description}") {{
                                           ioc {{ iocDescription }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(description, response['data']['iocCreate']['ioc']['iocDescription'])

    def test_graphql_create_ioc_should_allow_optional_tags_to_be_set(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        tags = 'tag1,tag2'
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}",
                                       tags: "{tags}") {{
                                           ioc {{ iocTags }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(tags, response['data']['iocCreate']['ioc']['iocTags'])

    # IOC are uniquely determined by their type/value
    def test_graphql_create_ioc_should_not_update_tags_when_creating_the_same_ioc_twice(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                           ioc {{ iocId iocDescription }}
                             }}
                         }}'''
        }
        self._subject.execute_graphql_query(payload)
        case = self._subject.create_case()
        case_identifier = case['case_id']
        tags = 'tag1,tag2'
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}",
                                       tags: "{tags}") {{
                                           ioc {{ iocId iocTags }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertIsNone(response['data']['iocCreate']['ioc']['iocTags'])

    def test_graphql_update_ioc_should_update_tlp(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                           ioc {{ iocId }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        ioc_identifier = response['data']['iocCreate']['ioc']['iocId']
        payload = {
            'query': f'''mutation {{
                             iocUpdate(iocId: {ioc_identifier}, caseId: {case_identifier},
                                       typeId: 1, tlpId: 2, value: "{ioc_value}") {{
                                           ioc {{ iocTlpId }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(2, response['data']['iocUpdate']['ioc']['iocTlpId'])

    def test_graphql_update_ioc_should_update_optional_parameter_description(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                           ioc {{ iocId }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        ioc_identifier = response['data']['iocCreate']['ioc']['iocId']
        description = 'some description'
        payload = {
            'query': f'''mutation {{
                             iocUpdate(iocId: {ioc_identifier}, caseId: {case_identifier},
                                       typeId: 1, tlpId: 2, value: "{ioc_value}", description: "{description}") {{
                                           ioc {{ iocDescription }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(description, response['data']['iocUpdate']['ioc']['iocDescription'])

    def test_graphql_update_ioc_should_update_optional_parameter_tags(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                           ioc {{ iocId }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        ioc_identifier = response['data']['iocCreate']['ioc']['iocId']
        tags = 'tag1,tag2'
        payload = {
            'query': f'''mutation {{
                             iocUpdate(iocId: {ioc_identifier}, caseId: {case_identifier},
                                       typeId: 1, tlpId: 2, value: "{ioc_value}", tags: "{tags}") {{
                                           ioc {{ iocTags }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(tags, response['data']['iocUpdate']['ioc']['iocTags'])

    def test_graphql_case_should_return_a_case_by_its_identifier(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        payload = {
            'query': f'''{{
                             case(caseId: {case_identifier}) {{
                                  caseId
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(case_identifier, response['data']['case']['caseId'])

    def test_graphql_iocs_should_return_all_iocs_of_a_case(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                           ioc {{ iocId }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        ioc_identifier = response['data']['iocCreate']['ioc']['iocId']
        payload = {
            'query': f'''{{
                             case(caseId: {case_identifier}) {{
                                 iocs {{ iocId }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(ioc_identifier, response['data']['case']['iocs'][0]['iocId'])

    def test_graphql_case_should_return_error_log_uuid_when_permission_denied(self):
        user = self._subject.create_user()
        case = self._subject.create_case()
        case_identifier = case['case_id']
        payload = {
            'query': f'''{{
                             case(caseId: {case_identifier}) {{
                                  caseId
                             }}
                         }}'''
        }
        response = user.execute_graphql_query(payload)
        self.assertRegex(response['errors'][0]['message'], r'Permission denied \(EID [0-9a-f-]{36}\)')

    def test_graphql_create_case_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                                caseCreate(name: "case2", description: "Some description", clientId: 1) {{
                                              case {{ caseId }}
                                }}
                            }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertNotIn('errors', body)

    def test_graphql_delete_case_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                                           caseCreate(name: "case2", description: "Some description", clientId: 1) {{
                                                         case {{ caseId }}
                                           }}
                                       }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        case_identifier = response['data']['caseCreate']['case']['caseId']
        payload2 = {
            'query': f'''mutation {{
                                   caseDelete(caseId: {case_identifier}) {{
                                                 case {{ caseId }}
                                   }}
                               }}'''
        }
        body = self._subject.execute_graphql_query(payload2)
        self.assertNotIn('errors', body)

    def test_graphql_update_case_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                                   caseUpdate(caseId: 1, name: "new name" ) {{
                                                 case {{ caseId }}
                                   }}
                               }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertNotIn('errors', body)

    def test_graphql_create_case_should_use_optionals_parameters(self):
        payload = {
            'query': f'''mutation {{
                                        caseCreate(name: "case2", description: "Some description", clientId: 1, 
                                        socId: "1", classificationId : 1) {{
                                                      case {{ caseId }}
                                        }}
                                    }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertNotIn('errors', body)

    def test_graphql_update_case_should_use_optionals_parameters(self):
        payload = {
            'query': f'''mutation {{
                                        caseUpdate(caseId: 1, description: "Some description", clientId: 1, 
                                        socId: "1", classificationId : 1) {{
                                                      case {{ caseId }}
                                        }}
                                    }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertNotIn('errors', body)

    def test_graphql_cases_should_return_newly_created_case(self):
        payload = {
            'query': f'''mutation {{
                                caseCreate(name: "case2", description: "Some description", clientId: 1) {{
                                              case {{ caseId }}
                                }}
                            }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        case_identifier = response['data']['caseCreate']['case']['caseId']
        payload = {
            'query': '{ cases { caseId} }'
        }
        response = self._subject.execute_graphql_query(payload)
        case_identifiers = []
        for case in response['data']['cases']:
            case_identifiers.append(case['caseId'])
        self.assertIn(case_identifier, case_identifiers)

    def test_graphql_update_case_should_update_optional_parameter_description(self):
        payload = {
            'query': f'''mutation {{
                                               caseCreate(name: "case2", description: "Some description", clientId: 1, 
                                               socId: "1", classificationId : 1) {{
                                                             case {{ caseId }}
                                               }}
                                           }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        case_identifier = body['data']['caseCreate']['case']['caseId']
        description = 'some description'
        payload = {
            'query': f'''mutation {{
                        caseUpdate(caseId: {case_identifier}, description: "{description}") {{
                                           case {{ description }}
                                               }}
                                           }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(description, response['data']['caseUpdate']['case']['description'])

    def test_graphql_update_case_should_update_optional_parameter_socId(self):
        payload = {
            'query': f'''mutation {{
                                               caseCreate(name: "case2", description: "Some description", clientId: 1, 
                                               socId: "1", classificationId : 1) {{
                                                             case {{ caseId }}
                                               }}
                                           }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        case_identifier = body['data']['caseCreate']['case']['caseId']
        socId = '17'
        payload = {
            'query': f'''mutation {{
                        caseUpdate(caseId: {case_identifier}, socId: "{socId}") {{
                                           case {{ socId }}
                                               }}
                                           }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(socId, response['data']['caseUpdate']['case']['socId'])

    def test_graphql_update_case_should_update_optional_parameter_classificationId(self):
        payload = {
            'query': f'''mutation {{
                                               caseCreate(name: "case2", description: "Some description", clientId: 1, 
                                               socId: "1", classificationId : 1) {{
                                                             case {{ caseId }}
                                               }}
                                           }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        case_identifier = body['data']['caseCreate']['case']['caseId']
        classificationId = 2
        payload = {
            'query': f'''mutation {{
                        caseUpdate(caseId: {case_identifier}, classificationId: {classificationId}) {{
                                           case {{ classificationId }}
                                               }}
                                           }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(2, response['data']['caseUpdate']['case']['classificationId'])

    def test_graphql_update_case_with_optional_parameter_severityId(self):
        payload = {
            'query': f'''mutation {{
                                        caseUpdate(caseId: 1, severityId: 1) {{
                                                      case {{ caseId }}
                                        }}
                                    }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertNotIn('errors', body)

    def test_graphql_update_case_with_optional_parameter_stateId_and_ownerId_reviewerId(self):
        payload = {
            'query': f'''mutation {{
                                        caseUpdate(caseId: 1, stateId: 1, ownerId: 1, reviewerId: 1) {{
                                                      case {{ caseId }}
                                        }}
                                    }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertNotIn('errors', body)

    def test_graphql_update_case_with_optional_parameter_tags(self):
        payload = {
            'query': f'''mutation {{
                                        caseUpdate(caseId: 1,tags: "test") {{
                                                      case {{ caseId }}
                                        }}
                                    }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertNotIn('errors', body)

    def test_graphql_update_case_with_optional_parameter_reviewStatusId(self):
        payload = {
            'query': f'''mutation {{
                                        caseUpdate(caseId: 1,tags: "test", reviewStatusId: 1) {{
                                                      case {{ caseId }}
                                        }}
                                    }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertNotIn('errors', body)