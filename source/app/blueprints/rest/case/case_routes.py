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


import binascii
import marshmallow
import traceback
from flask import Blueprint
from flask import request
from flask_login import current_user
from sqlalchemy import and_
from sqlalchemy import desc
from werkzeug import Response


from app import app
from app import db
from app import socket_io
from app.blueprints.rest.parsing import parse_comma_separated_identifiers
from app.blueprints.rest.parsing import parse_boolean
from app.blueprints.rest.endpoints import endpoint_deprecated
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_error
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.business.cases import cases_create
from app.business.cases import cases_delete
from app.business.errors import BusinessProcessingError
from app.datamgmt.case.case_db import case_exists
from app.datamgmt.case.case_db import get_review_id_from_name
from app.datamgmt.case.case_db import case_get_desc_crc
from app.datamgmt.case.case_db import get_case
from app.datamgmt.manage.manage_cases_db import get_filtered_cases
from app.datamgmt.manage.manage_groups_db import add_case_access_to_group
from app.datamgmt.manage.manage_groups_db import get_group_with_members
from app.datamgmt.manage.manage_users_db import get_user
from app.datamgmt.manage.manage_users_db import get_users_list_restricted_from_case
from app.datamgmt.manage.manage_users_db import set_user_case_access
from app.business.cases import cases_export_to_json
from app.iris_engine.access_control.utils import ac_fast_check_user_has_case_access
from app.iris_engine.access_control.utils import ac_set_case_access_for_users
from app.iris_engine.utils.tracker import track_activity
from app.models import CaseStatus
from app.models import ReviewStatusList
from app.models import UserActivity
from app.models.authorization import CaseAccessLevel
from app.models.authorization import Permissions
from app.models.authorization import User
from app.schema.marshables import TaskLogSchema
from app.schema.marshables import CaseSchema
from app.schema.marshables import CaseDetailsSchema
from app.schema.marshables import CaseSchemaForAPIV2
from app.blueprints.access_controls import ac_requires_case_identifier
from app.blueprints.access_controls import ac_api_requires
from app.util import add_obj_history_entry
from app.util import ac_api_return_access_denied
from app.util import response_error
from app.util import response_success

case_rest_blueprint = Blueprint('case_rest', __name__)

log = app.logger


@case_rest_blueprint.route('/case/exists', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/cases/<int:identifier>')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_exists_r(caseid):

    if case_exists(caseid):
        return response_success('Case exists')
    return response_error('Case does not exist', 404)


@case_rest_blueprint.route('/case/summary/update', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def desc_fetch(caseid):

    js_data = request.get_json()
    case = get_case(caseid)
    if not case:
        return response_error('Invalid case ID')

    case.description = js_data.get('case_description')
    crc = binascii.crc32(case.description.encode('utf-8'))
    db.session.commit()
    track_activity("updated summary", caseid)

    if not request.cookies.get('session'):
        # API call so we propagate the message to everyone
        data = {
            "case_description": case.description,
            "last_saved": current_user.user
        }
        socket_io.emit('save', data, to=f"case-{caseid}")

    return response_success("Summary updated", data=crc)


@case_rest_blueprint.route('/case/summary/fetch', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def summary_fetch(caseid):
    desc_crc32, description = case_get_desc_crc(caseid)

    return response_success("Summary fetch", data={'case_description': description, 'crc32': desc_crc32})


@case_rest_blueprint.route('/case/activities/list', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def activity_fetch(caseid):
    ua = UserActivity.query.with_entities(
        UserActivity.activity_date,
        User.name,
        UserActivity.activity_desc,
        UserActivity.is_from_api
    ).filter(and_(
        UserActivity.case_id == caseid,
        UserActivity.display_in_ui == True
    )).join(
        UserActivity.user
    ).order_by(
        desc(UserActivity.activity_date)
    ).limit(40).all()

    output = [a._asdict() for a in ua]

    return response_success("", data=output)


@case_rest_blueprint.route('/case/export', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def export_case(caseid):
    return response_success('', data=cases_export_to_json(caseid))


@case_rest_blueprint.route('/case/meta', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def meta_case(caseid):
    case_details = get_case(caseid)
    return response_success('', data=CaseDetailsSchema().dump(case_details))


@case_rest_blueprint.route('/case/tasklog/add', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_add_tasklog(caseid):

    log_schema = TaskLogSchema()

    try:

        log_data = log_schema.load(request.get_json())

        ua = track_activity(log_data.get('log_content'), caseid, user_input=True)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    return response_success("Log saved", data=ua)


@case_rest_blueprint.route('/case/users/list', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_get_users(caseid):

    users = get_users_list_restricted_from_case(caseid)

    return response_success(data=users)


@case_rest_blueprint.route('/case/access/set-group', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def group_cac_set_case(caseid):

    data = request.get_json()
    if not data:
        return response_error('Invalid request')

    if data.get('case_id') != caseid:
        return response_error('Inconsistent case ID')

    case = get_case(caseid)
    if not case:
        return response_error('Invalid case ID')

    group_id = data.get('group_id')
    access_level = data.get('access_level')

    group = get_group_with_members(group_id)

    try:

        success, logs = add_case_access_to_group(group, [data.get('case_id')], access_level)

        if success:
            success, logs = ac_set_case_access_for_users(group.group_members, caseid, access_level)

    except Exception as e:
        log.error("Error while setting case access for group: {}".format(e))
        log.error(traceback.format_exc())
        return response_error(msg=str(e))

    if success:
        track_activity("case access set to {} for group {}".format(data.get('access_level'), group_id), caseid)
        add_obj_history_entry(case, "access changed to {} for group {}".format(data.get('access_level'), group_id),
                              commit=True)

        return response_success(msg=logs)

    return response_error(msg=logs)


@case_rest_blueprint.route('/case/access/set-user', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def user_cac_set_case(caseid):

    data = request.get_json()
    if not data:
        return response_error("Invalid request")

    if data.get('user_id') == current_user.id:
        return response_error("I can't let you do that, Dave")

    user = get_user(data.get('user_id'))
    if not user:
        return response_error("Invalid user ID")

    if data.get('case_id') != caseid:
        return response_error("Inconsistent case ID")

    case = get_case(caseid)
    if not case:
        return response_error('Invalid case ID')

    try:

        success, logs = set_user_case_access(user.id, data.get('case_id'), data.get('access_level'))
        track_activity("case access set to {} for user {}".format(data.get('access_level'), user.name), caseid)
        add_obj_history_entry(case, "access changed to {} for user {}".format(data.get('access_level'), user.name))

        db.session.commit()

    except Exception as e:
        log.error("Error while setting case access for user: {}".format(e))
        log.error(traceback.format_exc())
        return response_error(msg=str(e))

    if success:
        return response_success(msg=logs)

    return response_error(msg=logs)


@case_rest_blueprint.route('/case/update-status', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_update_status(caseid):

    case = get_case(caseid)
    if not case:
        return response_error('Invalid case ID')

    status = request.get_json().get('status_id')
    case_status = {item.value for item in CaseStatus}

    try:
        status = int(status)
    except ValueError:
        return response_error('Invalid status')
    except TypeError:
        return response_error('Invalid status. Expected int')

    if status not in case_status:
        return response_error('Invalid status')

    case.status_id = status
    add_obj_history_entry(case, f'status updated to {CaseStatus(status).name}')

    db.session.commit()

    return response_success("Case status updated", data=case.status_id)


@case_rest_blueprint.route('/case/review/update', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_review(caseid):

    case = get_case(caseid)
    if not case:
        return response_error('Invalid case ID')

    action = request.get_json().get('action')
    reviewer_id = request.get_json().get('reviewer_id')

    if action == 'start':
        review_name = ReviewStatusList.review_in_progress
    elif action in ('cancel', 'request'):
        review_name = ReviewStatusList.pending_review
    elif action == 'no_review':
        review_name = ReviewStatusList.no_review_required
    elif action == 'to_review':
        review_name = ReviewStatusList.not_reviewed
    elif action == 'done':
        review_name = ReviewStatusList.reviewed
    else:
        return response_error('Invalid action')

    case.review_status_id = get_review_id_from_name(review_name)
    if reviewer_id:
        try:
            reviewer_id = int(reviewer_id)
        except ValueError:
            return response_error('Invalid reviewer ID')

        if not ac_fast_check_user_has_case_access(reviewer_id, caseid, [CaseAccessLevel.full_access]):
            return response_error('Invalid reviewer ID')

        case.reviewer_id = reviewer_id

    db.session.commit()

    add_obj_history_entry(case, f'review status updated to {review_name}')
    track_activity(f'review status updated to {review_name}', caseid)

    db.session.commit()

    return response_success("Case review updated", data=CaseSchema().dump(case))


@case_rest_blueprint.route('/api/v2/cases', methods=['POST'])
@ac_api_requires(Permissions.standard_user)
def create_case():
    try:
        case, _ = cases_create(request.get_json())
        return response_api_created(CaseSchemaForAPIV2().dump(case))
    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), e.get_data())


@case_rest_blueprint.route('/api/v2/cases', methods=['GET'])
@ac_api_requires()
def get_cases() -> Response:
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    case_ids_str = request.args.get('case_ids', None, type=parse_comma_separated_identifiers)
    order_by = request.args.get('order_by', type=str)
    sort_dir = request.args.get('sort_dir', 'asc', type=str)


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
    is_open = request.args.get('is_open', None, type=parse_boolean)

    filtered_cases = get_filtered_cases(
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
        search_value='',
        page=page,
        per_page=per_page,
        current_user_id=current_user.id,
        sort_by=order_by,
        sort_dir=sort_dir,
        is_open=is_open
    )
    if filtered_cases is None:
        return response_api_error('Filtering error')

    cases = {
        'total': filtered_cases.total,
        # TODO should maybe really uniform all return types of paginated list and replace field cases by field data
        'data': CaseSchemaForAPIV2().dump(filtered_cases.items, many=True),
        'last_page': filtered_cases.pages,
        'current_page': filtered_cases.page,
        'next_page': filtered_cases.next_num if filtered_cases.has_next else None,
    }

    return response_api_success(data=cases)


@case_rest_blueprint.route('/api/v2/cases/<int:identifier>', methods=['GET'])
@ac_api_requires()
def case_routes_get(identifier):
    case = get_case(identifier)
    if not case:
        return response_api_not_found()
    if not ac_fast_check_current_user_has_case_access(identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=identifier)
    return response_api_success(CaseSchemaForAPIV2().dump(case))


@case_rest_blueprint.route('/api/v2/cases/<int:identifier>', methods=['DELETE'])
@ac_api_requires(Permissions.standard_user)
def case_routes_delete(identifier):
    if not ac_fast_check_current_user_has_case_access(identifier, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=identifier)

    try:
        cases_delete(identifier)
        return response_api_deleted()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
