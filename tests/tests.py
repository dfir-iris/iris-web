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

    def test_graphql_endpoint_should_reject_requests_with_wrong_authentication_token(self):
        graphql_api = GraphQLApi(API_URL + '/graphql', 64*'0')
        payload = {
            'query': f'''query {{ cases  {{ edges {{ node {{ name }} }} }} }}'''
        }
        response = graphql_api.execute(payload)
        self.assertEqual(401, response.status_code)

    def test_graphql_cases_should_contain_the_initial_case(self):
        payload = {
            'query': f'''query {{ cases {{ edges {{ node {{ name }} }} }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        case_names = []
        for case in body['data']['cases']['edges']:
            case_names.append(case['node']['name'])
        self.assertIn('#1 - Initial Demo', case_names)

    def _get_first_case(self, body):
        for case in body['data']['cases']['edges']:
            if case['node']['name'] == '#1 - Initial Demo':
                return case

    def test_graphql_cases_should_have_a_global_identifier(self):
        payload = {
            'query': f'''query {{ cases {{ edges {{ node {{ id name }} }} }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        first_case = self._get_first_case(body)
        self.assertEqual(b64encode(b'CaseObject:1').decode(), first_case['node']['id'])

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
        test_ioc_value = response['data']['iocCreate']['ioc']['iocValue']
        self.assertEqual(test_ioc_value, ioc_value)

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

    def test_graphql_update_ioc_should_not_update_typeId(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                ioc {{ iocId iocTypeId }}
                            }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        ioc_identifier = response['data']['iocCreate']['ioc']['iocId']
        ioc_type = response['data']['iocCreate']['ioc']['iocTypeId']
        payload = {
            'query': f'''mutation {{
                             iocUpdate(iocId: {ioc_identifier}, caseId: {case_identifier},
                                 tlpId:1, value: "{ioc_value}") {{
                                     ioc {{ iocTypeId }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(ioc_type, response['data']['iocUpdate']['ioc']['iocTypeId'])

    def test_graphql_update_ioc_should_not_update_caseId(self):
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
                             iocUpdate(iocId: {ioc_identifier}, typeId:1,
                                 tlpId:1, value: "{ioc_value}") {{
                                     ioc {{ iocTlpId }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertIn('errors', response)

    def test_graphql_update_ioc_should_not_update_iocId(self):
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
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''mutation {{
                             iocUpdate(caseId: {case_identifier}, typeId:1,
                                 tlpId:1, value: "{ioc_value}") {{
                                     ioc {{ iocTlpId }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertIn('errors', response)

    def test_graphql_update_ioc_should_not_update_tlpId(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                ioc {{ iocId iocTlpId }}
                            }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        ioc_identifier = response['data']['iocCreate']['ioc']['iocId']
        ioc_tlp = response['data']['iocCreate']['ioc']['iocTlpId']
        payload = {
            'query': f'''mutation {{
                             iocUpdate(iocId: {ioc_identifier}, caseId: {case_identifier}, typeId:1,
                                  value: "{ioc_value}") {{
                                     ioc {{ iocId iocTlpId }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(ioc_tlp, response['data']['iocUpdate']['ioc']['iocTlpId'])

    def test_graphql_update_ioc_should_not_update_value(self):
        case = self._subject.create_case()
        case_identifier = case['case_id']
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                ioc {{ iocId iocValue }}
                            }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        ioc_identifier = response['data']['iocCreate']['ioc']['iocId']
        ioc_value = response['data']['iocCreate']['ioc']['iocValue']
        payload = {
            'query': f'''mutation {{
                             iocUpdate(iocId: {ioc_identifier}, caseId: {case_identifier}, typeId:1,
                                  tlpId:1) {{
                                     ioc {{ iocValue }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(ioc_value, response['data']['iocUpdate']['ioc']['iocValue'])

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
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''{{
                            case(caseId: {case_identifier}) {{
                                iocs {{ edges {{ node {{ iocId }} }} }}
                            }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertNotIn('errors', response)

    def test_graphql_iocs_should_return_linked_iocs_of_a_case(self):
        case_identifier = 1
        case_identifier_2 = 2
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f''' mutation {{ 
                                     caseCreate(name: "case2", description: "test", clientId: 1) {{
                                     case {{ description }}
                                }}
                            }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                 ioc {{ iocId }}
                             }}
                         }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''mutation {{
                                    iocCreate(caseId: {case_identifier_2}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                        ioc {{ iocId }}
                                    }}
                                }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''{{
                            case(caseId: {case_identifier}) {{
                                iocs(LinkedCases: 1) {{ edges {{ node {{ iocId }} }} }}
                            }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertNotIn('errors', response)

    def test_graphql_case_should_return_error_log_uuid_when_permission_denied(self):
        user = self._subject.create_user(self._generate_new_dummy_user_name())
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

    def test_graphql_case_should_return_error_ioc_when_permission_denied(self):
        user = self._subject.create_user(self._generate_new_dummy_user_name())
        payload = {
            'query': f''' mutation {{
                                                     caseCreate(name: "case", description: "test_ioc", clientId: 1) {{
                                                     case {{ caseId }}
                                                }}
                                            }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        case_identifier = body['data']['caseCreate']['case']['caseId']
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f'''mutation {{
                                     iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                         ioc {{ iocId iocValue }}
                                     }}
                                 }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''{{
                                    case(caseId: {case_identifier}) {{
                                        iocs {{ totalCount edges {{ node {{ iocId }} }} }}
                                    }}
                                 }}'''
        }
        response = user.execute_graphql_query(payload)
        self.assertIn('errors', response)

    def test_graphql_create_case_should_not_fail(self):
        test_description = 'description 2'
        payload = {
            'query': f''' mutation {{ 
                             caseCreate(name: "case2", description: "{test_description}", clientId: 1) {{
                             case {{ description }}
                        }}
                    }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        description = body['data']['caseCreate']['case']['description']
        self.assertEqual(description, test_description)

    def test_graphql_delete_case_should_not_fail(self):
        payload = {
            'query': '''mutation {
                            caseCreate(name: "case2", description: "Some description", clientId: 1) {
                                case { caseId }
                            } 
                        }'''
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
        self._subject.execute_graphql_query(payload2)
        payload = {
            'query': f''' mutation {{
                             caseUpdate(caseId:  {case_identifier}, name: "test_delete_case") {{
                                  case {{ name }}
                             }} 
                        }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertIn('errors', body)

    def test_graphql_delete_case_should_fail(self):
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
                                   caseDelete(caseId: {case_identifier}, cur_id: 1) {{
                                                 case {{ caseId }}
                                   }}
                               }}'''
        }
        body = self._subject.execute_graphql_query(payload2)
        self.assertIn('errors', body)

    def test_graphql_update_case_should_not_fail(self):
        test_name = 'new name'
        final_name = '#1 - new name'
        payload = {
            'query': f''' mutation {{
                     caseUpdate(caseId: 1, name: "{test_name}") {{
                          case {{ name }}
                     }} 
                }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        name = body['data']['caseUpdate']['case']['name']
        self.assertEqual(name, final_name)

    def test_graphql_create_case_should_use_optionals_parameters(self):
        id_client = 1
        payload = {
            'query': f''' mutation {{
                             caseCreate(name: "case2", description: "Some description", clientId: {id_client}, 
                             socId: "1", classificationId : 1) {{
                                 case {{ clientId }}
                             }} 
                        }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        client_id = body['data']['caseCreate']['case']['clientId']
        self.assertEqual(client_id, id_client)

    def test_graphql_update_case_should_use_optionals_parameters(self):
        id_case = 1
        payload = {
            'query': f'''mutation {{
                             caseUpdate(caseId: {id_case}, description: "Some description", clientId: 1, socId: "1",
                             classificationId : 1) {{
                             case {{ caseId }}
                          }}
                     }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        case_id = body['data']['caseUpdate']['case']['caseId']
        self.assertEqual(case_id, id_case)

    def test_graphql_cases_should_return_newly_created_case(self):
        payload = {
            'query': ''' mutation { caseCreate(name: "case2", description: "Some description", clientId: 1) {
                             case { caseId }
                          } 
                     }'''
        }
        response = self._subject.execute_graphql_query(payload)
        case_identifier = response['data']['caseCreate']['case']['caseId']
        payload = {
            'query': f'''query {{ cases {{ edges {{ node {{ caseId }} }} }} }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        case_identifiers = []
        for case in response['data']['cases']['edges']:
            case_identifiers.append(case['node']['caseId'])
        self.assertIn(case_identifier, case_identifiers)

    def test_graphql_update_case_should_update_optional_parameter_description(self):
        payload = {
            'query': ''' mutation { caseCreate(name: "case2", description: "Some description", clientId: 1, socId: "1",
                         classificationId : 1) {
                             case { caseId }
                         }
                    }'''
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
            'query': ''' mutation {
                             caseCreate(name: "case2", description: "Some description", clientId: 1, socId: "1",
                             classificationId : 1) {
                                 case { caseId }
                             } 
                       }'''
        }
        body = self._subject.execute_graphql_query(payload)
        case_identifier = body['data']['caseCreate']['case']['caseId']
        soc_id = '17'
        payload = {
            'query': f'''mutation {{
                             caseUpdate(caseId: {case_identifier}, socId: "{soc_id}") {{
                                 case {{ socId }}
                             }}
                       }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(soc_id, response['data']['caseUpdate']['case']['socId'])

    def test_graphql_update_case_should_update_optional_parameter_classificationId(self):
        payload = {
            'query': ''' mutation {
                             caseCreate(name: "case2", description: "Some description", clientId: 1, socId: "1",
                             classificationId : 1) {
                                 case { caseId } 
                             } 
                        }'''
        }
        body = self._subject.execute_graphql_query(payload)
        case_identifier = body['data']['caseCreate']['case']['caseId']
        classification_id = 2
        payload = {
            'query': f'''mutation {{
                        caseUpdate(caseId: {case_identifier}, classificationId: {classification_id}) {{
                            case {{ classificationId }}
                        }}
                  }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(2, response['data']['caseUpdate']['case']['classificationId'])

    def test_graphql_update_case_with_optional_parameter_severityId(self):
        payload = {
            'query': ''' mutation {
                         caseUpdate(caseId: 1, severityId: 1) { 
                             case { severityId } 
                         } 
                    }'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertEqual(1, body['data']['caseUpdate']['case']['severityId'])

    def test_graphql_update_case_with_optional_parameter_ownerId(self):
        payload = {
            'query': ''' mutation {
                             caseUpdate(caseId: 1, ownerId: 1) { 
                                 case { ownerId } 
                             } 
                        }'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertEqual(1, body['data']['caseUpdate']['case']['ownerId'])

    def test_graphql_update_case_with_optional_parameter_stateId_reviewerId(self):
        payload = {
            'query': ''' mutation {
                         caseUpdate(caseId: 1, reviewerId: 1) { 
                             case { reviewerId } 
                         } 
                     }'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertEqual(1, body['data']['caseUpdate']['case']['reviewerId'])

    def test_graphql_update_case_with_optional_parameter_stateId(self):
        payload = {
            'query': ''' mutation { 
                             caseUpdate(caseId: 1, stateId: 1) { 
                                 case { stateId } 
                             } 
                        }'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertEqual(1, body['data']['caseUpdate']['case']['stateId'])

    def test_graphql_update_case_with_optional_parameter_reviewStatusId(self):
        payload = {
            'query': '''mutation {
                            caseUpdate(caseId: 1, reviewStatusId: 1) { 
                                case { reviewStatusId } 
                            } 
                        }'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertEqual(1, body['data']['caseUpdate']['case']['reviewStatusId'])

    def test_graphql_query_ioc_should_not_fail(self):
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
            'query': f'''query {{
                                ioc(iocId: {ioc_identifier}) {{ iocValue }}
                                }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        self.assertEqual(ioc_value, body['data']['ioc']['iocValue'])

    def test_graphql_cases_should_not_fail(self):
        test_name = '#1 - Initial Demo'
        payload = {
            'query': '{ cases(first: 1) { edges { node { id name } } } }'
        }
        body = self._subject.execute_graphql_query(payload)
        for case in body['data']['cases']['edges']:
            name = case['node']['name']
            self.assertEqual(test_name, name)

    def test_graphql_update_ioc_should_update_misp(self):
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
                                 typeId: 1, tlpId: 2, iocMisp: "test", value: "{ioc_value}") {{
                                     ioc {{ iocMisp }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual("test", response['data']['iocUpdate']['ioc']['iocMisp'])

    def test_graphql_update_ioc_should_update_userId(self):
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
                                 typeId: 1, tlpId: 2, userId: 1, value: "{ioc_value}") {{
                                     ioc {{ userId }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual(1, response['data']['iocUpdate']['ioc']['userId'])

    def test_graphql_update_ioc_should_update_iocEnrichment(self):
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
                                 typeId: 1, tlpId: 2, iocEnrichment: "test", value: "{ioc_value}") {{
                                     ioc {{ iocEnrichment }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        self.assertEqual('"test"', response['data']['iocUpdate']['ioc']['iocEnrichment'])

    def test_graphql_update_ioc_should_update_modificationHistory(self):
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
                                 typeId: 1, tlpId: 2, modificationHistory: "test", value: "{ioc_value}") {{
                                     ioc {{ modificationHistory }}
                             }}
                         }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        print(response)
        self.assertEqual('"test"', response['data']['iocUpdate']['ioc']['modificationHistory'])

    def test_cursor_first_after(self):
        payload = {
            'query': f'''mutation {{
                         caseCreate(name: "case2", description: "Some description", clientId: 1, 
                                    socId: "1", classificationId : 1) {{
                                                 case {{ caseId }}
                                                       }}
                                                   }}'''
        }
        self._subject.execute_graphql_query(payload)
        case_id = 2
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''query {{ cases
                     {{ edges {{ node {{ caseId name }} cursor }} }} }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''query {{ cases(first:1, after:"YXJyYXljb25uZWN0aW9uOjA=")
             {{ edges {{ node {{ caseId }} cursor }} }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for case in body['data']['cases']['edges']:
            test_case_id = case['node']['caseId']
            self.assertEqual(case_id, test_case_id)

    def test_graphql_cases_classificationId_should_not_fail(self):
        classification_id = 1
        payload = {
            'query': f'''mutation {{
                                 caseCreate(name: "case1", description: "Some description", clientId: 1, 
                                            socId: "1", classificationId : {classification_id}) {{
                                                         case {{ caseId }}
                                                               }}
                                                           }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''mutation {{
                                         caseCreate(name: "case2", description: "Some description", clientId: 1, 
                                                    socId: "1", classificationId : 3) {{
                                                                 case {{ caseId classificationId}}
                                                                       }}
                                                                   }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''mutation {{
                                         caseCreate(name: "case3", description: "Some description", clientId: 1, 
                                                    socId: "1", classificationId : {classification_id}) {{
                                                                 case {{ classificationId }}
                                                                       }}
                                                                   }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''query {{ cases(classificationId: {classification_id} )
                     {{ edges {{ node {{ name caseId classificationId }} cursor }} }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for case in body['data']['cases']['edges']:
            test_classification = case['node']['classificationId']
            self.assertEqual(classification_id, test_classification)

    def test_graphql_cases_filter_clientId_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                         caseCreate(name: "case2", description: "Some description", clientId: 1, 
                                    socId: "1", classificationId : 1) {{
                                                 case {{ clientId }}
                                                       }}
                                                   }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        client_id = response['data']['caseCreate']['case']['clientId']
        payload = {
            'query': f'''query {{ cases(clientId: {client_id}) {{ edges {{ node {{ clientId }} }} }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for case in body['data']['cases']['edges']:
            test_client = case['node']['clientId']
            self.assertEqual(client_id, test_client)

    def test_graphql_cases_filter_stateId_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                         caseCreate(name: "case2", description: "Some description", clientId: 1, 
                                    socId: "1", classificationId : 1) {{
                                                 case {{ stateId }}
                                                       }}
                                                   }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        state_id = response['data']['caseCreate']['case']['stateId']
        payload = {
            'query': f'''query {{ cases(stateId: {state_id}) 
                    {{ edges {{ node {{ stateId }} }} }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for case in body['data']['cases']['edges']:
            test_state = case['node']['stateId']
            self.assertEqual(state_id, test_state)

    def test_graphql_cases_filter_ownerId_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                         caseCreate(name: "case2", description: "Some description", clientId: 1, 
                                    socId: "1", classificationId : 1) {{
                                                 case {{ ownerId }}
                                                       }}
                                                   }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        owner_id = response['data']['caseCreate']['case']['ownerId']
        payload = {
            'query': f'''query {{ cases(ownerId: {owner_id}) 
                    {{ edges {{ node {{ ownerId }} }} }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for case in body['data']['cases']['edges']:
            test_owner = case['node']['ownerId']
            self.assertEqual(owner_id, test_owner)

    def test_graphql_cases_filter_openDate_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                         caseCreate(name: "case2", description: "Some description", clientId: 1, 
                                    socId: "1", classificationId : 1) {{
                                                 case {{ openDate }}
                                                       }}
                                                   }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        open_date = response['data']['caseCreate']['case']['openDate']
        payload = {
            'query': f'''query {{ cases(openDate: "{open_date}") 
                    {{ edges {{ node {{ openDate }} }} }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for case in body['data']['cases']['edges']:
            test_date = case['node']['openDate']
            self.assertEqual(open_date, test_date)

    def test_graphql_cases_filter_name_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                         caseCreate(name: "case2", description: "Some description", clientId: 1, 
                                    socId: "1", classificationId : 1) {{
                                                 case {{ name }}
                                                       }}
                                                   }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        name = response['data']['caseCreate']['case']['name']
        payload = {
            'query': f'''query {{ cases(name: "{name}") 
                    {{ edges {{ node {{ name }} }} }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for case in body['data']['cases']['edges']:
            test_name = case['node']['name']
            self.assertEqual(name, test_name)

    def test_graphql_cases_filter_socId_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                         caseCreate(name: "case2", description: "Some description", clientId: 1, 
                                    socId: "1", classificationId : 1) {{
                                                 case {{ socId }}
                                                       }}
                                                   }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        soc_id = response['data']['caseCreate']['case']['socId']
        payload = {
            'query': f'''query {{ cases(socId: "{soc_id}") 
                    {{ edges {{ node {{ socId }} }} }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for case in body['data']['cases']['edges']:
            test_soc_id = case['node']['socId']
            self.assertEqual(soc_id, test_soc_id)

    def test_graphql_cases_filter_severityId_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                         caseCreate(name: "case2", description: "Some description", clientId: 1, 
                                    socId: "1", classificationId : 1) {{
                                                 case {{ severityId }}
                                                       }}
                                                   }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        severity_id = response['data']['caseCreate']['case']['severityId']
        payload = {
            'query': f'''query {{ cases(severityId: {severity_id}) 
                    {{ edges {{ node {{ severityId }} }} }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for case in body['data']['cases']['edges']:
            test_severity = case['node']['severityId']
            self.assertEqual(severity_id, test_severity)

    def test_graphql_cases_parameter_totalCount_should_not_fail(self):
        payload = {
            'query': f'''query {{ cases {{ totalCount }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        test_total = body['data']['cases']['totalCount']
        payload = {
            'query': f'''mutation {{
                                 caseCreate(name: "case2", description: "Some description", clientId: 1, 
                                            socId: "1", classificationId : 1) {{
                                                         case {{ name }}
                                                               }}
                                                           }}'''
        }
        self._subject.execute_graphql_query(payload)
        test_total += 1
        payload = {
            'query': f'''query {{ cases {{ totalCount }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        total = body['data']['cases']['totalCount']
        self.assertEqual(total, test_total)

    def test_graphql_iocs_filter_iocId_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                                        iocCreate(caseId: 1, typeId: 1, tlpId: 1, value: "33") {{
                                                      ioc {{ iocId }}
                                        }}
                                    }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        ioc_id = response['data']['iocCreate']['ioc']['iocId']
        payload = {
            'query': f'''{{
                                case(caseId: 1) {{
                                   iocs(iocId: 11) {{ edges {{ node {{ iocId }} }} }} }} 
                                   }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for ioc in body['data']['case']['iocs']['edges']:
            test_ioc_id = ioc['node']['iocId']
            self.assertEqual(ioc_id, test_ioc_id)

    def test_graphql_iocs_filter_iocUuid_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                                        iocCreate(caseId: 1, typeId: 1, tlpId: 1, value: "33") {{
                                                      ioc {{ iocUuid iocId }}
                                        }}
                                    }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        ioc_uuid = response['data']['iocCreate']['ioc']['iocUuid']
        payload = {
            'query': f'''{{
                                case(caseId: 1) {{
                                   iocs(iocUuid: "{ioc_uuid}") {{ edges {{ node {{ iocId iocUuid }}
                                    }} }} }} 
                                   }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for ioc in body['data']['case']['iocs']['edges']:
            test_ioc_uuid = ioc['node']['iocUuid']
            self.assertEqual(ioc_uuid, test_ioc_uuid)

    def test_graphql_iocs_filter_iocValue_should_not_fail(self):
        ioc_value = 'test'
        payload = {
            'query': f'''mutation {{
                iocCreate(caseId: 1, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                    ioc {{ iocValue }}
                    }}
                }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''mutation {{
                        iocCreate(caseId: 1, typeId: 2, tlpId: 1, value: "{ioc_value}") {{
                            ioc {{ iocValue }}
                            }}
                        }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''mutation {{
                        iocCreate(caseId: 1, typeId: 1, tlpId: 1, value: "testtest") {{
                            ioc {{ iocValue }}
                            }}
                        }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''{{
               case(caseId: 1) {{
                     iocs(iocValue: "{ioc_value}") {{ edges {{ node {{ iocValue iocId }} }} }} }} 
                  }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for ioc in body['data']['case']['iocs']['edges']:
            test_ioc_value = ioc['node']['iocValue']
            self.assertEqual(ioc_value, test_ioc_value)

    def test_graphql_iocs_filter_first_should_not_fail(self):
        ioc_value = 'IOC value #1'
        compte = 1
        payload = {
            'query': f'''mutation {{
                iocCreate(caseId: 1, typeId: 1, tlpId: 1, value: "test2") {{
                    ioc {{ iocValue }}
                    }}
                }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''mutation {{
                        iocCreate(caseId: 1, typeId: 1, tlpId: 1, value: "testtest") {{
                            ioc {{ iocValue }}
                            }}
                        }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''{{
               case(caseId: 1) {{
                     iocs(first: {compte}) {{ edges {{ node {{ iocValue iocId }} }} }} }} 
                  }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for ioc in body['data']['case']['iocs']['edges']:
            value = ioc['node']['iocValue']
            self.assertEqual(ioc_value, value)

    def test_graphql_iocs_filter_iocTypeId_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                     iocCreate(caseId: 1, typeId: 1, tlpId: 1, value: "test") {{
                                   ioc {{ iocTypeId }}
                             }}
                     }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        ioc_type_id = response['data']['iocCreate']['ioc']['iocTypeId']
        payload = {
            'query': f'''{{
                       case(caseId: 1) {{
                           iocs(iocTypeId: {ioc_type_id}) {{ edges {{ node {{ iocTypeId }} }} }} }} 
                         }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for ioc in body['data']['case']['iocs']['edges']:
            test_type_id = ioc['node']['iocTypeId']
            self.assertEqual(test_type_id, ioc_type_id)

    def test_graphql_iocs_filter_iocDescription_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                     iocCreate(caseId: 1, typeId: 1, tlpId: 1, value: "test") {{
                                   ioc {{ iocDescription }}
                             }}
                     }}'''
        }
        self._subject.execute_graphql_query(payload)
        description = 'Some description'
        payload = {
            'query': f'''mutation {{
                                     iocUpdate(iocId:1, caseId: 1, description: "{description}", typeId:1, tlpId:1, 
                                     value: "test") {{
                                             ioc {{ iocDescription }}
                                     }}
                                 }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''{{
                       case(caseId: 1) {{
                           iocs(iocDescription: "{description}") {{ edges {{ node {{ iocDescription }} }} }} }} 
                         }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for ioc in body['data']['case']['iocs']['edges']:
            test_description = ioc['node']['iocDescription']
            self.assertEqual(test_description, description)

    def test_graphql_iocs_filter_iocTlpId_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                     iocCreate(caseId: 1, typeId: 1, tlpId: 1, value: "test") {{
                                   ioc {{ iocTlpId }}
                             }}
                     }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        ioc_tlp_id = response['data']['iocCreate']['ioc']['iocTlpId']
        payload = {
            'query': f'''{{
                       case(caseId: 1) {{
                           iocs(iocTlpId: {ioc_tlp_id}) {{ edges {{ node {{ iocTlpId }} }} }} }} 
                         }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for ioc in body['data']['case']['iocs']['edges']:
            test_tlp_id = ioc['node']['iocTlpId']
            self.assertEqual(test_tlp_id, ioc_tlp_id)

    def test_graphql_iocs_filter_iocTags_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                     iocCreate(caseId: 1, typeId: 1, tlpId: 1, value: "test") {{
                                   ioc {{ iocTags }}
                             }}
                     }}'''
        }
        self._subject.execute_graphql_query(payload)
        tags = "test"
        payload = {
            'query': f'''mutation {{
                                             iocUpdate(iocId:1, caseId: 1, description: "Some description", typeId:1, 
                                             tlpId:1, value: "test", tags :"{tags}") {{
                                                     ioc {{ iocTags }}
                                             }}
                                         }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''{{
                       case(caseId: 1) {{
                           iocs(iocTags: "{tags}") {{ edges {{ node {{ iocTags }} }} }} }} 
                         }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for ioc in body['data']['case']['iocs']['edges']:
            test_tags = ioc['node']['iocTags']
            self.assertEqual(test_tags, tags)

    def test_graphql_iocs_filter_iocMisp_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                     iocCreate(caseId: 1, typeId: 1, tlpId: 1, value: "test") {{
                                   ioc {{ iocMisp }}
                             }}
                     }}'''
        }
        self._subject.execute_graphql_query(payload)
        misp = "test"
        payload = {
            'query': f'''{{
                       case(caseId: 1) {{
                           iocs(iocMisp: "{misp}") {{ edges {{ node {{ iocMisp }} }} }} }} 
                         }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for ioc in body['data']['case']['iocs']['edges']:
            test_misp = ioc['node']['iocMisp']
            self.assertNotEqual(test_misp, misp)

    def test_graphql_iocs_filter_userId_should_not_fail(self):
        payload = {
            'query': f'''mutation {{
                        iocCreate(caseId: 1, typeId: 1, tlpId: 1, value: "test") {{
                                      ioc {{ userId }}
                                }}
                        }}'''
        }
        response = self._subject.execute_graphql_query(payload)
        user_id = response['data']['iocCreate']['ioc']['userId']
        payload = {
            'query': f'''{{
                          case(caseId: 1) {{
                              iocs(userId: {user_id}) {{ edges {{ node {{ userId }} }} }} }} 
                            }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for ioc in body['data']['case']['iocs']['edges']:
            test_user = ioc['node']['userId']
            self.assertEqual(test_user, user_id)

    def test_graphql_iocs_should_return_linked_iocs(self):
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f''' mutation {{ 
                                     caseCreate(name: "case2", description: "test", clientId: 1) {{
                                     case {{ caseId }}
                                }}
                            }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        case_identifier = body['data']['caseCreate']['case']['caseId']
        payload = {
            'query': f''' mutation {{ 
                                             caseCreate(name: "case3", description: "test", clientId: 1) {{
                                             case {{ caseId }}
                                        }}
                                    }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        case_identifier_2 = body['data']['caseCreate']['case']['caseId']
        ioc_value = self._generate_new_dummy_ioc_value()
        payload = {
            'query': f'''mutation {{
                             iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                 ioc {{ iocId iocValue }}
                             }}
                         }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''mutation {{
                                     iocCreate(caseId: {case_identifier}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                         ioc {{ iocId iocValue }}
                                     }}
                                 }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''mutation {{
                                            iocCreate(caseId: {case_identifier_2}, typeId: 1, tlpId: 1, value: "{ioc_value}") {{
                                                ioc {{ iocId iocValue }}
                                            }}
                                        }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''{{
                            case(caseId: {case_identifier}) {{
                                iocs(LinkedCases: {case_identifier_2}) {{ totalCount edges {{ node {{ iocId }} }} }}
                            }}
                         }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        total_count = body['data']['case']['iocs']['totalCount']
        self.assertEqual(1, total_count)

    def test_graphql_case_should_return_error_cases_query_when_permission_denied(self):
        user = self._subject.create_user(self._generate_new_dummy_user_name())
        name = "cases_query_permission_denied"
        case_id = None
        payload = {
            'query': f'''mutation {{
                                    caseCreate(name: "{name}", description: "Some description", clientId: 1) {{
                                                                 case {{ caseId }}
                                        }}
                                    }}'''
        }
        self._subject.execute_graphql_query(payload)
        payload = {
            'query': f'''query {{ cases (name :"{name}")
                            {{ edges {{ node {{ caseId }} }} }} }}'''
        }
        body = user.execute_graphql_query(payload)
        for case in body['data']['cases']['edges']:
            test_case_id = case['node']['caseId']
            self.assertEqual(case_id, test_case_id)

    def test_graphql_case_should_return_success_cases_query(self):
        user = self._subject.create_user(self._generate_new_dummy_user_name())
        name = "cases_query_permission_denied"
        payload = {
            'query': f'''mutation {{
                                    caseCreate(name: "{name}", description: "Some description", clientId: 1) {{
                                                                 case {{ caseId }}
                                        }}
                                    }}'''
        }
        body = user.execute_graphql_query(payload)
        case_id = body['data']['caseCreate']['case']['caseId']
        payload = {
            'query': f'''query {{ cases (name :"{name}")
                            {{ edges {{ node {{ caseId }} }} }} }}'''
        }
        body = user.execute_graphql_query(payload)
        for case in body['data']['cases']['edges']:
            test_case_id = case['node']['caseId']
            self.assertEqual(case_id, test_case_id)

    def test_graphql_case_should_work_with_tags(self):
        payload = {
            'query': f'''mutation {{
                                    caseCreate(name: "test_case_tag", description: "Some description", clientId: 1) {{
                                                                 case {{ caseId }}
                                        }}
                                    }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        case_id = body['data']['caseCreate']['case']['caseId']
        self._subject.update_case(case_id, {'case_tags': 'test_case_number1'})
        payload = {
            'query': f'''query {{ cases (tags :"test_case_number1")
                            {{ edges {{ node {{ caseId }} }} }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for case in body['data']['cases']['edges']:
            test_case_id = case['node']['caseId']
            self.assertEqual(case_id, test_case_id)

    def test_graphql_case_should_work_with_open_since(self):
        payload = {
            'query': f'''mutation {{
                                    caseCreate(name: "test_case_open_since", description: "Some description", clientId: 1) {{
                                                                         case {{ caseId }}
                                        }}
                                    }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        case_id = body['data']['caseCreate']['case']['caseId']
        payload = {
            'query': f'''query {{ cases (openSince: 0, name: "test_case_open_since") {{ edges {{ node {{ caseId initialDate openDate }} }} }} }}'''
        }
        body = self._subject.execute_graphql_query(payload)
        for case in body['data']['cases']['edges']:
            test = case['node']['caseId']
            self.assertEqual(test, case_id)

    def test_graphql_manage_case_filter_api_rest_should_fail(self):
        self._subject.create_case()
        response = self._subject.get_cases_filter()
        self.assertEqual('success', response['status'])
