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
from datetime import datetime

import marshmallow
from flask import Blueprint
from flask import request
from flask_login import current_user

from app import db
from app.blueprints.rest.case_comments import case_comment_update
from app.blueprints.rest.endpoints import endpoint_deprecated
from app.business.errors import BusinessProcessingError
from app.business.tasks import tasks_delete
from app.business.tasks import tasks_create
from app.business.tasks import tasks_get
from app.business.tasks import tasks_update
from app.datamgmt.case.case_tasks_db import add_comment_to_task
from app.datamgmt.case.case_tasks_db import delete_task_comment
from app.datamgmt.case.case_tasks_db import get_case_task_comment
from app.datamgmt.case.case_tasks_db import get_case_task_comments
from app.datamgmt.case.case_tasks_db import get_task
from app.datamgmt.case.case_tasks_db import get_tasks_status
from app.datamgmt.case.case_tasks_db import get_tasks_with_assignees
from app.datamgmt.case.case_tasks_db import update_task_status
from app.datamgmt.manage.manage_cases_db import execute_and_save_action
from app.datamgmt.manage.manage_task_response_db import get_task_responses_list, get_task_response_by_id
from app.datamgmt.states import get_tasks_state
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import CaseTaskSchema
from app.schema.marshables import CommentSchema
from app.blueprints.access_controls import ac_requires_case_identifier
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success

case_tasks_rest_blueprint = Blueprint('case_tasks_rest', __name__)


@case_tasks_rest_blueprint.route('/case/tasks/list', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/cases/<int:case_identifier>/tasks')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_get_tasks(caseid: int):
    ct = get_tasks_with_assignees(caseid)

    if not ct:
        output = []
    else:
        output = ct

    ret = {
        "tasks_status": get_tasks_status(),
        "tasks": output,
        "state": get_tasks_state(caseid=caseid)
    }

    return response_success("", data=ret)


@case_tasks_rest_blueprint.route('/case/tasks/state', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_get_tasks_state(caseid: int):
    os = get_tasks_state(caseid=caseid)
    if os:
        return response_success(data=os)
    return response_error('No tasks state for this case.')


@case_tasks_rest_blueprint.route('/case/tasks/status/update/<int:cur_id>', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_task_status_update(cur_id: int, caseid: int):
    task = get_task(task_id=cur_id)
    if not task:
        return response_error("Invalid task ID for this case")

    if request.is_json:

        if update_task_status(request.json.get('task_status_id'), cur_id, caseid):
            task_schema = CaseTaskSchema()

            return response_success("Task status updated", data=task_schema.dump(task))
        return response_error("Invalid status")

    return response_error("Invalid request")


@case_tasks_rest_blueprint.route('/case/tasks/add', methods=['POST'])
@endpoint_deprecated('POST', '/api/v2/cases/<int:caseid>/tasks')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def deprecated_case_add_task(caseid: int):
    task_schema = CaseTaskSchema()
    try:
        msg, task = tasks_create(case_identifier=caseid,
                                 request_json=request.get_json())
        return response_success(msg, data=task_schema.dump(task))
    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@case_tasks_rest_blueprint.route('/case/tasks/<int:cur_id>', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/cases/<int:case_identifier>/tasks/<int:cur_id>')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def deprecated_case_task_view(cur_id: int, caseid: int):
    task = get_task(task_id=cur_id)
    if not task:
        return response_error('Invalid task ID for this case')

    task_schema = CaseTaskSchema()

    return response_success(data=task_schema.dump(task))


@case_tasks_rest_blueprint.route('/case/tasks/update/<int:cur_id>', methods=['POST'])
@endpoint_deprecated('PUT', '/api/v2/cases/<int:case_identifier>/tasks/<int:identifier>')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def deprecated_case_edit_task(cur_id: int, caseid: int):
    try:
        task = get_task(task_id=cur_id)
        if not task:
            return response_error(msg='Invalid task ID for this case')

        task = tasks_update(task, request.get_json())
        task_schema = CaseTaskSchema()

        return response_success(msg='Task updated', data=task_schema.dump(task))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg='Data error', data=e.messages)


@case_tasks_rest_blueprint.route('/case/tasks/delete/<int:cur_id>', methods=['POST'])
@endpoint_deprecated('DELETE', '/api/v2/cases/<int:case_identifier>/tasks/<int:cur_id>')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def deprecated_case_delete_task(cur_id: int, caseid: int):
    try:
        task = tasks_get(identifier=cur_id)
        tasks_delete(task)
        return response_success('Task deleted')
    except BusinessProcessingError as e:
        return response_error(msg=e.get_message(), data=e.get_data())


@case_tasks_rest_blueprint.route('/case/tasks/<int:cur_id>/comments/list', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_task_list(cur_id: int, caseid: int):

    task_comments = get_case_task_comments(task_id=cur_id)
    if task_comments is None:
        return response_error('Invalid task ID')

    return response_success(data=CommentSchema(many=True).dump(task_comments))


@case_tasks_rest_blueprint.route('/case/tasks/<int:cur_id>/comments/add', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_task_add(cur_id: int, caseid: int):

    try:
        task = get_task(task_id=cur_id)
        if not task:
            return response_error('Invalid task ID')

        comment_schema = CommentSchema()

        comment = comment_schema.load(request.get_json())
        comment.comment_case_id = caseid
        comment.comment_user_id = current_user.id
        comment.comment_date = datetime.now()
        comment.comment_update_date = datetime.now()
        db.session.add(comment)
        db.session.commit()

        add_comment_to_task(task.id, comment.comment_id)

        db.session.commit()

        hook_data = {
            "comment": comment_schema.dump(comment),
            "task": CaseTaskSchema().dump(task)
        }
        call_modules_hook('on_postload_task_commented', data=hook_data, caseid=caseid)

        track_activity(f"task \"{task.task_title}\" commented", caseid=caseid)
        return response_success("Task commented", data=comment_schema.dump(comment))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages())


@case_tasks_rest_blueprint.route('/case/tasks/<int:cur_id>/comments/<int:com_id>', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_task_get(cur_id: int, com_id: int, caseid: int):

    comment = get_case_task_comment(task_id=cur_id,
                                    comment_id=com_id)
    if not comment:
        return response_error("Invalid comment ID")

    return response_success(data=comment._asdict())


@case_tasks_rest_blueprint.route('/case/tasks/<int:cur_id>/comments/<int:com_id>/edit', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_task_edit(cur_id: int, com_id: int, caseid: int):

    return case_comment_update(comment_id=com_id, object_type='tasks', caseid=caseid)


@case_tasks_rest_blueprint.route('/case/tasks/<int:cur_id>/comments/<int:com_id>/delete', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_task_delete(cur_id: int, com_id: int, caseid: int):

    success, msg = delete_task_comment(task_id=cur_id, comment_id=com_id)
    if not success:
        return response_error(msg)

    call_modules_hook('on_postload_task_comment_delete', data=com_id, caseid=caseid)

    track_activity(f"comment {com_id} on task {cur_id} deleted", caseid=caseid)
    return response_success(msg)


@case_tasks_rest_blueprint.route('/case/tasks/action_responses/<int:cur_id>', methods=['GET'])
@ac_api_requires()
def case_task_action_response(cur_id):
    # Retrieve the list of task action responses
    task_action_responses = get_task_responses_list(cur_id)

    for response in task_action_responses:
        # Serialize 'created_at' field if it is a datetime object
        if isinstance(response.get('created_at'), datetime):
            response['created_at'] = response['created_at'].strftime("%Y-%m-%d %H:%M:%S")

        # Serialize 'updated_at' field if it is a datetime object
        if isinstance(response.get('updated_at'), datetime):
            response['updated_at'] = response['updated_at'].strftime("%Y-%m-%d %H:%M:%S")

        # Handle 'body' field serialization
        if 'body' in response:
            try:
                # Attempt to serialize 'body' if it's a dictionary or list
                if isinstance(response['body'], (dict, list)):
                    response['body'] = json.dumps(response['body'])
            except (TypeError, ValueError):
                # If serialization fails, convert it to a string
                response['body'] = str(response['body'])

    # Return a successful response with serialized task action responses
    return response_success("success", task_action_responses)


@case_tasks_rest_blueprint.route('/case/jsoneditor', methods=['POST'])
def save_data():
    try:
        data = request.get_json()

        if not isinstance(data, dict):
            raise ValueError("Request payload is not a valid JSON object")

        payload = data.get('payload')
        task_id = data.get('task_id')
        action_id = data.get('action_id')

        if not payload or not task_id or not action_id:
            raise KeyError("Missing one or more required keys: 'payload', 'task_id', 'action_id'")

        action_response = execute_and_save_action(payload, task_id, action_id)
        return response_success("ac_requires_case_identifier", action_response)
    except KeyError as e:
        return response_error(f"Missing key: {e}")
    # except ValueError as e:
    #     return jsonify({"status": "error", "message": str(e)}), 400
    # except Exception as e:
    #     return jsonify({"status": "error", "message": str(e)})

@case_tasks_rest_blueprint.route('/case/tasks/action_response/<int:task_id>', methods=['GET'])
def case_task_action_response_by_id(task_id):
    action_response = get_task_response_by_id(task_id)

    if action_response:
        return response_success("Task action response fetched successfully", data=action_response)
    else:
        return response_error("No action response found for this task", 404)