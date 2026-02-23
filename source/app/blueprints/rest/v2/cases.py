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

import json
import urllib.parse
from typing import Any

from flask import Blueprint
from flask import request
from marshmallow import ValidationError
from werkzeug import Response

from app.blueprints.rest.parsing import parse_comma_separated_identifiers
from app.blueprints.rest.parsing import parse_boolean
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.blueprints.rest.v2.case_routes.assets import case_assets_blueprint
from app.blueprints.rest.v2.case_routes.iocs import case_iocs_blueprint
from app.blueprints.rest.v2.case_routes.notes import case_notes_blueprint
from app.blueprints.rest.v2.case_routes.notes_directories import case_notes_directories_blueprint
from app.blueprints.rest.v2.case_routes.tasks import case_tasks_blueprint
from app.blueprints.rest.v2.case_routes.evidences import case_evidences_blueprint
from app.blueprints.rest.v2.case_routes.events import case_events_blueprint
from app.blueprints.iris_user import iris_current_user
from app.business.cases import cases_create
from app.business.cases import cases_delete
from app.business.cases import cases_get_by_identifier
from app.business.cases import cases_update
from app.models.errors import BusinessProcessingError, ObjectNotFoundError
from app.business.cases import cases_filter
from app.schema.marshables import CaseSchemaForAPIV2
from app.schema.marshables import CaseDetailsSchema
from app.datamgmt.manage.manage_cases_db import get_filtered_cases
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_current_user_has_customer_access
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.access_controls import ac_api_return_access_denied
from app.models.authorization import Permissions
from app.models.authorization import CaseAccessLevel
from app.iris_engine.module_handler.module_handler import call_deprecated_on_preload_modules_hook


class CasesOperations:

    def __init__(self):
        self._schema = CaseSchemaForAPIV2()

    def search(self):
        pagination_parameters = parse_pagination_parameters(request)

        case_ids_str = request.args.get('case_ids', None, type=parse_comma_separated_identifiers)

        case_customer_id = request.args.get('case_customer_id', None, type=str)
        case_name = request.args.get('case_name', None, type=str)
        case_description = request.args.get('case_description', None, type=str)
        case_classification_id = request.args.get(
            'case_classification_id', None, type=int)
        case_owner_id = request.args.get('case_owner_id', None, type=int)
        case_opening_user_id = request.args.get(
            'case_opening_user_id', None, type=int)
        case_severity_id = request.args.get('case_severity_id', None, type=int)
        case_state_id = request.args.get('case_state_id', None, type=int)
        case_soc_id = request.args.get('case_soc_id', None, type=str)
        start_open_date = request.args.get('start_open_date', None, type=str)
        end_open_date = request.args.get('end_open_date', None, type=str)
        is_open = request.args.get('is_open', None, type=parse_boolean)

        filtered_cases = cases_filter(
            iris_current_user,
            pagination_parameters,
            case_name,
            case_ids_str,
            case_customer_id,
            case_description,
            case_classification_id,
            case_owner_id,
            case_opening_user_id,
            case_severity_id,
            case_state_id,
            case_soc_id,
            start_open_date,
            end_open_date,
            is_open
        )

        return response_api_paginated(self._schema, filtered_cases)

    def filter(self) -> Response:
        pagination_parameters = parse_pagination_parameters(request)

        logic = request.args.get('logic', 'and', type=str)
        logic = (logic or 'and').lower()
        if logic not in ('and', 'or'):
            return response_api_error("Invalid logic (expected 'and' or 'or')")

        raw_filters = request.args.get('filters', None, type=str)
        advanced_filters: list[dict[str, Any]] | None = None

        if raw_filters:
            try:
                decoded = urllib.parse.unquote(raw_filters)
                parsed = json.loads(decoded)
            except Exception:
                return response_api_error('Invalid filters JSON')

            if not isinstance(parsed, list):
                return response_api_error('Invalid filters (expected a JSON array)')

            advanced_filters = []
            for i, f in enumerate(parsed):
                if not isinstance(f, dict):
                    return response_api_error(f'Invalid filter at index {i} (expected object)')

                field_id = f.get('fieldId')
                operation = f.get('operation')
                value = f.get('value', '')

                if not isinstance(field_id, str) or not field_id:
                    return response_api_error(f'Invalid fieldId at index {i}')
                if not isinstance(operation, str) or not operation:
                    return response_api_error(f'Invalid operation at index {i}')
                if not isinstance(value, str):
                    return response_api_error(f'Invalid value at index {i}')

                operation = operation.lower()

                allowed_ops = {
                    'equals',
                    'not',
                    'starts_with',
                    'not_starts_with',
                    'contains',
                    'not_contains',
                    'ends_with',
                    'not_ends_with',
                    'empty',
                    'not_empty'
                }
                if operation not in allowed_ops:
                    return response_api_error(f'Invalid operation at index {i}')

                if operation in ('empty', 'not_empty'):
                    value = ''

                advanced_filters.append(
                    {
                        'fieldId': field_id,
                        'operation': operation,
                        'value': value
                    }
                )

        case_ids_str = request.args.get('case_ids', None, type=str)
        if case_ids_str:
            try:
                case_ids_str = parse_comma_separated_identifiers(case_ids_str)
            except ValueError:
                return response_api_error('Invalid case id')

        case_customer_id = request.args.get('case_customer_id', None, type=str)
        case_name = request.args.get('case_name', None, type=str)
        case_description = request.args.get('case_description', None, type=str)
        case_classification_id = request.args.get('case_classification_id', None, type=int)
        case_owner_id = request.args.get('case_owner_id', None, type=int)
        case_opening_user_id = request.args.get('case_opening_user_id', None, type=int)
        case_severity_id = request.args.get('case_severity_id', None, type=int)
        case_state_id = request.args.get('case_state_id', None, type=int)
        case_soc_id = request.args.get('case_soc_id', None, type=str)
        start_open_date = request.args.get('start_open_date', None, type=str)
        end_open_date = request.args.get('end_open_date', None, type=str)
        draw = request.args.get('draw', 1, type=int)
        search_value = request.args.get('search[value]', type=str)

        is_open_raw = request.args.get('is_open', None, type=str)
        is_open = None
        if is_open_raw is not None:
            v = is_open_raw.strip().lower()
            if v in ('1', 'true', 'yes', 'y', 'on'):
                is_open = True
            elif v in ('0', 'false', 'no', 'n', 'off'):
                is_open = False

        if type(draw) is not int:
            draw = 1

        filtered_cases = get_filtered_cases(
            iris_current_user.id,
            pagination_parameters,
            case_ids=case_ids_str,
            case_customer_id=case_customer_id,
            case_name=case_name,
            case_description=case_description,
            case_classification_id=case_classification_id,
            case_owner_id=case_owner_id,
            case_opening_user_id=case_opening_user_id,
            case_severity_id=case_severity_id,
            case_state_id=case_state_id,
            case_soc_id=case_soc_id,
            start_open_date=start_open_date,
            end_open_date=end_open_date,
            search_value=search_value,
            is_open=is_open,
            advanced_filters=advanced_filters,
            advanced_logic=logic
        )
        if filtered_cases is None:
            return response_api_error('Filtering error')

        cases_payload = {
            'total': filtered_cases.total,
            'cases': CaseDetailsSchema().dump(filtered_cases.items, many=True),
            'last_page': filtered_cases.pages,
            'current_page': filtered_cases.page,
            'next_page': filtered_cases.next_num if filtered_cases.has_next else None,
            'draw': draw
        }

        return response_api_success(cases_payload)

    def create(self):
        try:
            request_data = call_deprecated_on_preload_modules_hook('case_create', request.get_json())
            case = self._schema.load(request_data)
            case_template_id = request_data.pop('case_template_id', None)
            case = cases_create(iris_current_user, case, case_template_id)
            result = self._schema.dump(case)
            return response_api_created(result)
        except ValidationError as e:
            return response_api_error('Data error', e.messages)
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), e.get_data())

    def read(self, identifier):
        try:
            case = cases_get_by_identifier(identifier)
            if not ac_fast_check_current_user_has_case_access(identifier,
                                                              [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=identifier)
            result = self._schema.dump(case)
            return response_api_success(result)
        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, identifier):
        if not ac_fast_check_current_user_has_case_access(identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=identifier)

        try:
            case = cases_get_by_identifier(identifier)

            request_data = request.get_json()

            customer_identifier = request_data.get('case_customer_id')
            # If user tries to update the customer, check if the user has access to the new customer
            if customer_identifier and customer_identifier != case.client_id:
                if not ac_current_user_has_customer_access(customer_identifier):
                    raise BusinessProcessingError('Invalid customer ID. Permission denied.')

            if 'case_name' in request_data:
                short_case_name = request_data.get('case_name').replace(f'#{case.case_id} - ', '')
                request_data['case_name'] = f'#{case.case_id} - {short_case_name}'
            if not customer_identifier:
                request_data['case_customer_id'] = case.client_id
            reviewer_identifier = request_data.get('reviewer_id')
            if reviewer_identifier == '':
                request_data['reviewer_id'] = None

            updated_case = self._schema.load(request_data, instance=case, partial=True)

            protagonists = request_data.get('protagonists')
            tags = request_data.get('case_tags')
            case = cases_update(case, updated_case, protagonists, tags)
            result = self._schema.dump(case)
            return response_api_success(result)
        except ValidationError as e:
            return response_api_error('Data error', e.messages)
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), e.get_data())

    def delete(self, identifier):
        if not ac_fast_check_current_user_has_case_access(identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=identifier)

        try:
            cases_delete(identifier)
            return response_api_deleted()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), e.get_data())


# Create blueprint & import child blueprints
cases_blueprint = Blueprint('cases',
                            __name__,
                            url_prefix='/cases')
cases_blueprint.register_blueprint(case_assets_blueprint)
cases_blueprint.register_blueprint(case_iocs_blueprint)
cases_blueprint.register_blueprint(case_notes_directories_blueprint)
cases_blueprint.register_blueprint(case_notes_blueprint)
cases_blueprint.register_blueprint(case_tasks_blueprint)
cases_blueprint.register_blueprint(case_evidences_blueprint)
cases_blueprint.register_blueprint(case_events_blueprint)

cases_operations = CasesOperations()


@cases_blueprint.get('')
@ac_api_requires()
def get_cases() -> Response:
    return cases_operations.search()


@cases_blueprint.get('/filter')
@ac_api_requires()
def filter_cases() -> Response:
    return cases_operations.filter()


@cases_blueprint.post('')
@ac_api_requires(Permissions.standard_user)
def create_case():
    return cases_operations.create()


@cases_blueprint.get('/<int:identifier>')
@ac_api_requires()
def case_routes_get(identifier):
    return cases_operations.read(identifier)


@cases_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.standard_user)
def rest_v2_cases_update(identifier):
    return cases_operations.update(identifier)


@cases_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.standard_user)
def case_routes_delete(identifier):
    return cases_operations.delete(identifier)
