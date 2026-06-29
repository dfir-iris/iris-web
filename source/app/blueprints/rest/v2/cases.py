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
from app.business.activity import activity_search_in_case
from app.blueprints.rest.v2.case_routes.assets import case_assets_blueprint
from app.blueprints.rest.v2.case_routes.iocs import case_iocs_blueprint
from app.blueprints.rest.v2.case_routes.notes import case_notes_blueprint
from app.blueprints.rest.v2.case_routes.notes_directories import case_notes_directories_blueprint
from app.blueprints.rest.v2.case_routes.tasks import case_tasks_blueprint
from app.blueprints.rest.v2.case_routes.evidences import case_evidences_blueprint
from app.blueprints.rest.v2.case_routes.events import case_events_blueprint
from app.blueprints.rest.v2.case_routes.timelines import case_timelines_blueprint
from app.blueprints.rest.v2.case_routes.datastore import case_datastore_blueprint
from app.blueprints.iris_user import iris_current_user
from app.business.cases import cases_create
from app.business.cases import cases_close
from app.business.cases import cases_delete
from app.business.cases import cases_exists
from app.business.cases import cases_get_by_identifier
from app.business.cases import cases_reopen
from app.business.cases import cases_update
from app.datamgmt.manage.manage_users_db import get_users_list_restricted_from_case
from app.datamgmt.manage.manage_access_control_db import get_case_effective_access
from app.models.errors import BusinessProcessingError, ObjectNotFoundError
from app.business.cases import cases_filter
from app.schema.marshables import CaseSchemaForAPIV2
from app.schema.marshables import CaseDetailsSchema
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_current_user_has_customer_access
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.access_controls import ac_api_return_access_denied
from app.models.authorization import Permissions
from app.models.authorization import CaseAccessLevel
from app.iris_engine.module_handler.module_handler import call_deprecated_on_preload_modules_hook
from app.db import db


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
        start_close_date = request.args.get('start_close_date', None, type=str)
        end_close_date = request.args.get('end_close_date', None, type=str)
        is_open = request.args.get('is_open', None, type=parse_boolean)
        # Free-text search across case name, customer name, and (numeric) case id.
        # Powers the context switcher's search box; an empty / whitespace value is ignored.
        quick_search = request.args.get('quick_search', None, type=str)

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
            is_open,
            quick_search=quick_search,
            start_close_date=start_close_date,
            end_close_date=end_close_date,
        )

        return response_api_paginated(self._schema, filtered_cases)

    def filter(self) -> Response:
        pagination_parameters = parse_pagination_parameters(request)

        logic = request.args.get('logic', 'and', type=str)
        logic = (logic or 'and').lower()
        if logic not in ('and', 'or'):
            return response_api_error("Invalid logic (expected 'and' or 'or')")

        raw_filters = request.args.get('filters', None, type=str)
        advanced_filters: Any = None

        if raw_filters:
            try:
                decoded = urllib.parse.unquote(raw_filters)
                parsed = json.loads(decoded)
            except Exception:
                return response_api_error('Invalid filters JSON')

            # Accept either:
            #   * Legacy flat list of conditions combined by the
            #     top-level `logic` query param (`?logic=and`).
            #   * Nested group object: `{ logic, items: [<cond>|<group>] }`
            #     where groups can recurse arbitrarily deep.
            # The validator below normalises both into the nested form
            # so the SQL builder downstream only has to handle one
            # shape.
            ALLOWED_OPS = {
                'equals', 'not',
                'starts_with', 'not_starts_with',
                'contains', 'not_contains',
                'ends_with', 'not_ends_with',
                'empty', 'not_empty'
            }
            MAX_DEPTH = 8  # safety cap on recursion depth

            def _validate_condition(f: Any, path: str) -> dict[str, Any]:
                if not isinstance(f, dict):
                    raise ValueError(f'Invalid condition at {path} (expected object)')
                field_id = f.get('fieldId')
                operation = f.get('operation')
                value = f.get('value', '')

                if not isinstance(field_id, str) or not field_id:
                    raise ValueError(f'Invalid fieldId at {path}')
                if not isinstance(operation, str) or not operation:
                    raise ValueError(f'Invalid operation at {path}')
                if not isinstance(value, str):
                    raise ValueError(f'Invalid value at {path}')

                op = operation.lower()
                if op not in ALLOWED_OPS:
                    raise ValueError(f'Invalid operation at {path}')
                if op in ('empty', 'not_empty'):
                    value = ''

                return {'fieldId': field_id, 'operation': op, 'value': value}

            def _validate_group(node: Any, depth: int, path: str) -> dict[str, Any]:
                if depth > MAX_DEPTH:
                    raise ValueError(f'Filter group too deeply nested at {path}')
                if not isinstance(node, dict):
                    raise ValueError(f'Invalid group at {path} (expected object)')
                group_logic = str(node.get('logic', 'and')).lower()
                if group_logic not in ('and', 'or'):
                    raise ValueError(f"Invalid logic at {path} (expected 'and' or 'or')")
                items = node.get('items')
                if not isinstance(items, list):
                    raise ValueError(f'Invalid items at {path} (expected list)')

                normalised: list[dict[str, Any]] = []
                for i, item in enumerate(items):
                    sub_path = f'{path}.items[{i}]'
                    if isinstance(item, dict) and (
                        'items' in item or 'logic' in item and 'fieldId' not in item
                    ):
                        normalised.append(_validate_group(item, depth + 1, sub_path))
                    else:
                        normalised.append(_validate_condition(item, sub_path))

                return {'logic': group_logic, 'items': normalised}

            try:
                if isinstance(parsed, list):
                    # Legacy shape: wrap in a single root group whose
                    # logic is the page-level `logic` query param.
                    advanced_filters = _validate_group(
                        {'logic': logic, 'items': parsed}, 0, 'filters'
                    )
                elif isinstance(parsed, dict):
                    advanced_filters = _validate_group(parsed, 0, 'filters')
                else:
                    return response_api_error('Invalid filters (expected array or object)')
            except ValueError as e:
                return response_api_error(str(e))

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

        filtered_cases = cases_filter(
            iris_current_user,
            pagination_parameters,
            name=case_name,
            case_identifiers=case_ids_str,
            customer_identifier=case_customer_id,
            description=case_description,
            classification_identifier=case_classification_id,
            owner_identifier=case_owner_id,
            opening_user_identifier=case_opening_user_id,
            severity_identifier=case_severity_id,
            status_identifier=case_state_id,
            soc_identifier=case_soc_id,
            start_open_date=start_open_date,
            end_open_date=end_open_date,
            is_open=is_open,
            search_value=search_value,
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
            case = self._schema.load(request_data, session=db.session)
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
            request_data.pop('review_status', None)

            updated_case = self._schema.load(
                request_data,
                instance=case,
                partial=True,
                session=db.session
            )

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

    def close(self, identifier):
        if not ac_fast_check_current_user_has_case_access(identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=identifier)

        try:
            case = cases_close(identifier)
            return response_api_success(CaseDetailsSchema().dump(case))
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), e.get_data())

    def reopen(self, identifier):
        if not ac_fast_check_current_user_has_case_access(identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=identifier)

        try:
            case = cases_reopen(identifier)
            return response_api_success(CaseDetailsSchema().dump(case))
        except ObjectNotFoundError:
            return response_api_not_found()
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
cases_blueprint.register_blueprint(case_timelines_blueprint)
cases_blueprint.register_blueprint(case_datastore_blueprint)

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


@cases_blueprint.post('/<int:identifier>/close')
@ac_api_requires(Permissions.standard_user)
def case_routes_close(identifier):
    return cases_operations.close(identifier)


@cases_blueprint.post('/<int:identifier>/reopen')
@ac_api_requires(Permissions.standard_user)
def case_routes_reopen(identifier):
    return cases_operations.reopen(identifier)


@cases_blueprint.get('/<int:identifier>/access/users')
@ac_api_requires()
def list_case_access_users(identifier):
    """Return every user with effective access to this case along with
    their access level. Used by the frontend to populate task-assignee
    pickers and to surface who can see a given case.

    Access level is the integer enum from `CaseAccessLevel` (1 = deny,
    2 = read_only, 4 = full_access). Callers that need only assignable
    users typically filter on full_access (4) client-side, matching the
    legacy iris-web behaviour.
    """
    if not ac_fast_check_current_user_has_case_access(
        identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]
    ):
        return ac_api_return_access_denied(caseid=identifier)

    users = get_users_list_restricted_from_case(identifier)
    return response_api_success(users)


@cases_blueprint.get('/<int:identifier>/access/me')
@ac_api_requires()
def get_case_access_me(identifier):
    """Return the current user's effective access level for this case.

    The SPA reads this once per case load to gate edit/delete affordances
    before the user can attempt a 403. The integer matches `CaseAccessLevel`
    (1 = deny_all, 2 = read_only, 4 = full_access). A user with no row in
    `UserCaseEffectiveAccess` is treated as deny_all so the frontend can
    still render a coherent "no access" state.
    """
    if not cases_exists(identifier):
        return response_api_not_found()

    level = get_case_effective_access(iris_current_user.id, identifier)
    if level is None:
        level = CaseAccessLevel.deny_all.value
    return response_api_success({'access_level': int(level)})


@cases_blueprint.get('/<int:identifier>/followers')
@ac_api_requires()
def list_case_followers(identifier):
    """Return the users following this case.

    Each entry is `{user_id, user_name, user_login}`. The dashboard
    "Follow" toggle on the case header reads this list to render the
    current follower count and to highlight whether *you* are
    following.
    """
    from app.models.authorization import User
    from app.models.authorization import UserFollowedCase

    if not cases_exists(identifier):
        return response_api_not_found()
    if not ac_fast_check_current_user_has_case_access(
        identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]
    ):
        return ac_api_return_access_denied(caseid=identifier)

    rows = (
        db.session.query(User.id, User.user, User.name)
        .join(UserFollowedCase, UserFollowedCase.user_id == User.id)
        .filter(UserFollowedCase.case_id == identifier)
        .order_by(User.name.asc())
        .all()
    )
    return response_api_success(data=[
        {'user_id': r.id, 'user_login': r.user, 'user_name': r.name}
        for r in rows
    ])


@cases_blueprint.get('/<int:identifier>/war-rooms')
@ac_api_requires()
def list_case_war_rooms(identifier):
    """Return war rooms this case is attached to.

    Used by the case detail topbar to render the "in war room" badge +
    quick-jump menu. Read-only — gated by case read access.
    """
    from app.business.war_rooms import war_rooms_for_case
    from app.blueprints.rest.v2.war_rooms.serializers import serialize_case_war_room_summary

    if not cases_exists(identifier):
        return response_api_not_found()
    if not ac_fast_check_current_user_has_case_access(
        identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]
    ):
        return ac_api_return_access_denied(caseid=identifier)

    rows = war_rooms_for_case(identifier)
    return response_api_success(data=[serialize_case_war_room_summary(r) for r in rows])


@cases_blueprint.get('/<int:identifier>/activities')
@ac_api_requires()
def list_case_activities(identifier):
    """Return the recent user activity log for this case.

    Mirrors the legacy `/case/activities/list` endpoint, which the frontend
    uses to surface "people involved" on a case. Each row carries the user
    name, the activity date, the description and whether the entry was
    produced by an API caller.
    """
    if not cases_exists(identifier):
        return response_api_not_found()

    if not ac_fast_check_current_user_has_case_access(
        identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]
    ):
        return ac_api_return_access_denied(caseid=identifier)

    activities = activity_search_in_case(identifier)
    return response_api_success(activities)
