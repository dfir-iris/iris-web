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

from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.access_controls import ac_api_requires
from app.schema.marshables import CaseTaskSchema
from app.business.errors import BusinessProcessingError
from app.business.tasks import tasks_create
from app.models.authorization import CaseAccessLevel
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access

case_tasks_bp = Blueprint('case_tasks',
                          __name__,
                          url_prefix='/<int:case_id>/tasks')


@case_tasks_bp.post('', strict_slashes=False)
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
