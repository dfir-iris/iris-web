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
from app.business.errors import BusinessProcessingError
from app.datamgmt.case.case_tasks_db import delete_task
from app.datamgmt.case.case_tasks_db import get_task_with_assignees
from app.datamgmt.states import update_tasks_state
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity


def delete(identifier, context_case_identifier):
    call_modules_hook('on_preload_task_delete', data=identifier, caseid=context_case_identifier)
    task = get_task_with_assignees(task_id=identifier, case_id=context_case_identifier)
    if not task:
        raise BusinessProcessingError('Invalid task ID for this case')
    delete_task(identifier)
    update_tasks_state(caseid=context_case_identifier)
    call_modules_hook('on_postload_task_delete', data=identifier, caseid=context_case_identifier)
    track_activity(f"deleted task \"{task.task_title}\"")
    return 'Task deleted'
