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

from datetime import datetime

from flask_sqlalchemy.pagination import Pagination

from app.db import db
from app.blueprints.iris_user import iris_current_user
from app.datamgmt.case.case_tasks_db import delete_task
from app.datamgmt.case.case_tasks_db import list_user_tasks
from app.datamgmt.case.case_tasks_db import add_task
from app.datamgmt.case.case_tasks_db import update_task_assignees
from app.datamgmt.case.case_tasks_db import get_task
from app.datamgmt.case.case_tasks_db import get_filtered_tasks
from app.datamgmt.states import update_tasks_state
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.models import CaseTasks
from app.models.pagination_parameters import PaginationParameters
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


def tasks_delete(task: CaseTasks):
    call_modules_hook('on_preload_task_delete', task.id)

    delete_task(task.id)
    update_tasks_state(caseid=task.task_case_id)
    call_modules_hook('on_postload_task_delete', task.id, caseid=task.task_case_id)
    track_activity(f'deleted task "{task.task_title}"')


def tasks_create(task: CaseTasks, task_assignee_list) -> CaseTasks:

    ctask = add_task(task=task,
                     assignee_id_list=task_assignee_list,
                     user_id=iris_current_user.id,
                     caseid=task.task_case_id
                     )

    ctask = call_modules_hook('on_postload_task_create', ctask, caseid=task.task_case_id)
    if not ctask:
        raise BusinessProcessingError('Unable to create task for internal reasons')

    track_activity(f'added task "{ctask.task_title}"', caseid=task.task_case_id)
    return ctask


def tasks_get(identifier) -> CaseTasks:
    task = get_task(identifier)
    if not task:
        raise ObjectNotFoundError()
    return task


def tasks_filter(case_identifier, pagination_parameters: PaginationParameters) -> Pagination:
    return get_filtered_tasks(case_identifier, pagination_parameters)


def tasks_filter_by_user():
    return list_user_tasks(iris_current_user.id)


def tasks_update(task: CaseTasks, task_assignee_list):
    task.task_userid_update = iris_current_user.id
    task.task_last_update = datetime.utcnow()

    update_task_assignees(task.id, task_assignee_list, task.task_case_id)
    update_tasks_state(task.task_case_id)

    db.session.commit()

    task = call_modules_hook('on_postload_task_update', task, caseid=task.task_case_id)
    if not task:
        raise BusinessProcessingError('Unable to update task for internal reasons')

    track_activity(f'updated task "{task.task_title}" (status {task.status.status_name})', caseid=task.task_case_id)
    return task
