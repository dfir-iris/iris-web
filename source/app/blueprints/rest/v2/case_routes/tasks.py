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
from marshmallow import ValidationError

from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.blueprints.access_controls import ac_api_return_access_denied, ac_fast_check_current_user_has_case_access
from app.blueprints.access_controls import ac_api_requires
from app.schema.marshables import CaseTaskSchema
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.business.tasks import tasks_create
from app.business.tasks import tasks_get
from app.business.tasks import tasks_update
from app.business.tasks import tasks_delete
from app.business.tasks import tasks_filter
from app.models.authorization import CaseAccessLevel
from app.iris_engine.module_handler.module_handler import call_deprecated_on_preload_modules_hook


class TasksOperations:

    def __init__(self):
        self._schema = CaseTaskSchema()

    def search(self, case_identifier):
        if not ac_fast_check_current_user_has_case_access(case_identifier,
                                                          [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        pagination_parameters = parse_pagination_parameters(request)

        tasks = tasks_filter(case_identifier, pagination_parameters)

        return response_api_paginated(self._schema, tasks)

    def create(self, case_identifier):
        if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        request_data = call_deprecated_on_preload_modules_hook('task_create', request.get_json(), case_identifier)
        if 'task_assignee_id' in request_data or 'task_assignees_id' not in request_data:
            return response_api_error('task_assignee_id is not valid anymore since v1.5.0')
        task_assignee_list = request_data['task_assignees_id']
        del request_data['task_assignees_id']

        try:
            task = self._schema.load(request_data)
            task.task_case_id = case_identifier
            case = tasks_create(task, task_assignee_list)
            result = self._schema.dump(case)
            return response_api_created(result)

        except ValidationError as e:
            return response_api_error('Data error', e.messages)

        except BusinessProcessingError as e:
            return response_api_error(e.get_message())

    def read(self, case_identifier, identifier):
        try:
            task = tasks_get(identifier)

            if task.task_case_id != case_identifier:
                raise ObjectNotFoundError()

            if not ac_fast_check_current_user_has_case_access(task.task_case_id,
                                                              [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=task.task_case_id)

            result = self._schema.dump(task)
            return response_api_success(result)
        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, case_identifier, identifier):
        try:
            task = tasks_get(identifier)

            if task.task_case_id != case_identifier:
                raise ObjectNotFoundError()

            if not ac_fast_check_current_user_has_case_access(task.task_case_id,
                                                              [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=task.task_case_id)

            case_identifier = task.task_case_id
            request_data = call_deprecated_on_preload_modules_hook('task_update', request.get_json(), case_identifier)

            if 'task_assignee_id' in request_data or 'task_assignees_id' not in request_data:
                return response_api_error('task_assignee_id is not valid anymore since v1.5.0')

            task_assignee_list = request_data['task_assignees_id']
            del request_data['task_assignees_id']

            request_data['id'] = task.id
            task = self._schema.load(request_data, instance=task)

            task = tasks_update(task, task_assignee_list)

            result = self._schema.dump(task)
            return response_api_success(result)

        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())

    def delete(self, case_identifier, identifier):
        try:
            task = tasks_get(identifier)

            if task.task_case_id != case_identifier:
                raise ObjectNotFoundError()

            if not ac_fast_check_current_user_has_case_access(task.task_case_id, [CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=identifier)

            tasks_delete(task)
            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())


case_tasks_blueprint = Blueprint('case_tasks',
                                 __name__,
                                 url_prefix='/<int:case_identifier>/tasks')
tasks_operations = TasksOperations()


@case_tasks_blueprint.get('')
@ac_api_requires()
def case_get_tasks(case_identifier):
    return tasks_operations.search(case_identifier)


@case_tasks_blueprint.post('')
@ac_api_requires()
def add_case_task(case_identifier):
    return tasks_operations.create(case_identifier)


@case_tasks_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_case_task(case_identifier, identifier):
    return tasks_operations.read(case_identifier, identifier)


@case_tasks_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_case_task(case_identifier, identifier):
    return tasks_operations.update(case_identifier, identifier)


@case_tasks_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_case_task(case_identifier, identifier):
    return tasks_operations.delete(case_identifier, identifier)
