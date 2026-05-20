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

from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.access_controls import ac_api_return_access_denied
from app.business.tasks import tasks_delete
from app.business.tasks import tasks_get
from app.models.errors import ObjectNotFoundError
from app.models.errors import BusinessProcessingError
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import CaseTaskSchema
from app.blueprints.rest.v2.tasks_routes.comments import tasks_comments_blueprint


class Tasks:

    def __init__(self):
        self._schema = CaseTaskSchema()

    def read(self, identifier):

        try:
            task = tasks_get(identifier)

            if not ac_fast_check_current_user_has_case_access(task.task_case_id,
                                                              [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=task.task_case_id)

            result = self._schema.dump(task)
            return response_api_success(result)
        except ObjectNotFoundError:
            return response_api_not_found()

    def delete(self, identifier):
        try:
            task = tasks_get(identifier)

            if not ac_fast_check_current_user_has_case_access(task.task_case_id, [CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=identifier)

            tasks_delete(task)
            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())


tasks_blueprint = Blueprint('tasks', __name__, url_prefix='/tasks')
tasks_blueprint.register_blueprint(tasks_comments_blueprint)
tasks_operations = Tasks()


@tasks_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_case_task(identifier):
    return tasks_operations.read(identifier)


@tasks_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_case_task(identifier):
    return tasks_operations.delete(identifier)
