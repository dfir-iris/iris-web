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

from app import app
from app.db import db
from app import socket_io
from app.blueprints.rest.endpoints import endpoint_deprecated
from app.blueprints.iris_user import iris_current_user
from app.business.cases import cases_exists
from app.datamgmt.case.case_db import get_review_id_from_name
from app.datamgmt.case.case_db import case_get_desc_crc
from app.datamgmt.case.case_db import get_case
from app.datamgmt.manage.manage_groups_db import add_case_access_to_group
from app.datamgmt.manage.manage_groups_db import get_group_with_members
from app.datamgmt.manage.manage_users_db import get_user
from app.datamgmt.manage.manage_users_db import get_users_list_restricted_from_case
from app.business.access_controls import set_user_case_access, ac_fast_check_user_has_case_access
from app.business.activity import activity_search_in_case
from app.business.cases import cases_export_to_json
from app.iris_engine.access_control.utils import ac_set_case_access_for_users
from app.iris_engine.utils.tracker import track_activity
from app.models.cases import CaseStatus, ReviewStatusList
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import TaskLogSchema
from app.schema.marshables import CaseSchema
from app.schema.marshables import CaseDetailsSchema
from app.blueprints.access_controls import ac_requires_case_identifier
from app.blueprints.access_controls import ac_api_requires
from app.util import add_obj_history_entry
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success

case_rest_blueprint = Blueprint('case_rest', __name__)

log = app.logger


@case_rest_blueprint.route('/case/exists', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/cases/<int:identifier>')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_routes_exists(caseid):

    if cases_exists(caseid):
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
    track_activity('updated summary', caseid)

    if not request.cookies.get('session'):
        # API call so we propagate the message to everyone
        data = {
            'case_description': case.description,
            'last_saved': iris_current_user.user
        }
        socket_io.emit('save', data, to=f'case-{caseid}')

    return response_success('Summary updated', data=crc)


@case_rest_blueprint.route('/case/summary/fetch', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def summary_fetch(caseid):
    desc_crc32, description = case_get_desc_crc(caseid)

    return response_success('Summary fetch', data={'case_description': description, 'crc32': desc_crc32})


@case_rest_blueprint.route('/case/activities/list', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def activity_fetch(caseid):
    output = activity_search_in_case(caseid)

    return response_success('', data=output)


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
        return response_error(msg='Data error', data=e.messages)

    return response_success('Log saved', data=ua)


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
        log.error(f'Error while setting case access for group: {e}')
        log.error(traceback.format_exc())
        return response_error(msg=str(e))

    if success:
        track_activity('case access set to {} for group {}'.format(data.get('access_level'), group_id), caseid)
        add_obj_history_entry(case, 'access changed to {} for group {}'.format(data.get('access_level'), group_id),
                              commit=True)

        return response_success(msg=logs)

    return response_error(msg=logs)


@case_rest_blueprint.route('/case/access/set-user', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def user_cac_set_case(caseid):

    data = request.get_json()
    if not data:
        return response_error('Invalid request')

    if data.get('user_id') == iris_current_user.id:
        return response_error('I can\'t let you do that, Dave')

    user = get_user(data.get('user_id'))
    if not user:
        return response_error('Invalid user ID')

    if data.get('case_id') != caseid:
        return response_error('Inconsistent case ID')

    case = get_case(caseid)
    if not case:
        return response_error('Invalid case ID')

    try:

        case_identifier = data.get('case_id')
        access_level = data.get('access_level')

        if user.id is None or type(user.id) is not int:
            return response_error('Invalid user id')
        if case_identifier is None or type(case_identifier) is not int:
            return response_error('Invalid case id')
        if access_level is None or type(access_level) is not int:
            return response_error('Invalid access level')
        if CaseAccessLevel.has_value(access_level) is False:
            return response_error('Invalid access level')

        set_user_case_access(user.id, case_identifier, access_level)
        track_activity('case access set to {} for user {}'.format(data.get('access_level'), user.name), caseid)
        add_obj_history_entry(case, 'access changed to {} for user {}'.format(data.get('access_level'), user.name))

        db.session.commit()
        return response_success(msg=f'Case access set to {access_level} for user {user.id}')

    except Exception as e:
        log.error(f'Error while setting case access for user: {e}')
        log.error(traceback.format_exc())
        return response_error(str(e))


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

    return response_success('Case status updated', data=case.status_id)


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

    return response_success('Case review updated', data=CaseSchema().dump(case))
