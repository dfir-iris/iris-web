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

from flask import Blueprint
from flask import request

from app.blueprints.rest.endpoints import response_api_error, response_api_not_found, response_api_deleted
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.access_controls import ac_api_requires
from app.schema.marshables import CaseTaskSchema
from app.business.errors import BusinessProcessingError, ObjectNotFoundError
from app.business.tasks import tasks_create, tasks_get, tasks_delete
from app.models.authorization import CaseAccessLevel
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access

case_tasks_blueprint = Blueprint('case_tasks',
                                 __name__,
                                 url_prefix='/<int:case_id>/tasks')

@case_tasks_blueprint.post('')
@ac_api_requires()
def add_case_task(case_id):
    """
    Add a task to a case.

    Args:
        case_id (int): The Case ID for this task
    """
    if not ac_fast_check_current_user_has_case_access(case_id, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=case_id)

    task_schema = CaseTaskSchema()
    try:
        _, case = tasks_create(case_id, request.get_json())
        return response_api_created(task_schema.dump(case))
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())


@case_tasks_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_case_task(case_id, identifier):
    """
    Handles getting a task from a case.

    Args:
        case_id (int): The case ID
        identifier (int): The task ID
    """

    try:
        task = tasks_get(identifier)

        if task.task_case_id != case_id:
            raise ObjectNotFoundError()

        if not ac_fast_check_current_user_has_case_access(task.task_case_id, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=task.task_case_id)

        task_schema = CaseTaskSchema()
        return response_api_created(task_schema.dump(task))
    except ObjectNotFoundError:
        return response_api_not_found()


@case_tasks_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_case_task(case_id, identifier):
    """
    Handle deleting a task from a case

    Args:
        case_id (int): The case ID
        identifier (int): The task ID    
    """

    try:
        task = tasks_get(identifier)

        if task.task_case_id != case_id:
            raise ObjectNotFoundError()

        if not ac_fast_check_current_user_has_case_access(task.task_case_id, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=identifier)

        tasks_delete(task)
        return response_api_deleted()
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())


# TODO: Add task endpoint endpoint