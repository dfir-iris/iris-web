#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
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

from flask_sqlalchemy.pagination import Pagination

from app.models.errors import ObjectNotFoundError
from app.models.models import GlobalTasks
from datetime import datetime
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.datamgmt.db_operations import db_create
from app.datamgmt.global_tasks import filter_global_tasks
from app.datamgmt.global_tasks import get_global_task_by_identifier
from app.datamgmt.global_tasks import update_global_task
from app.datamgmt.global_tasks import delete_global_task
from app.models.pagination_parameters import PaginationParameters


def global_tasks_filter(pagination_parameters: PaginationParameters) -> Pagination:
    return filter_global_tasks(pagination_parameters)


def global_tasks_create(user, global_task: GlobalTasks) -> GlobalTasks:
    global_task.task_userid_update = user.id
    global_task.task_open_date = datetime.utcnow()
    global_task.task_last_update = datetime.utcnow()
    global_task.task_last_update = datetime.utcnow()

    db_create(global_task)

    global_task = call_modules_hook('on_postload_global_task_create', global_task)
    track_activity(f'created new global task "{global_task.task_title}"')

    return global_task


def global_tasks_get(identifier) -> GlobalTasks:
    task = get_global_task_by_identifier(identifier)
    if not task:
        raise ObjectNotFoundError()
    return task


def global_tasks_update(user, task: GlobalTasks) -> GlobalTasks:
    task.task_userid_update = user.id
    task.task_last_update = datetime.utcnow()

    update_global_task()

    task = call_modules_hook('on_postload_global_task_update', data=task)
    track_activity(f'updated global task {task.task_title} (status {task.task_status_id})')

    return task


def global_tasks_delete(task: GlobalTasks):
    call_modules_hook('on_preload_global_task_delete', task.id)

    delete_global_task(task)

    call_modules_hook('on_postload_global_task_delete', task)
    track_activity(f'deleted global task ID {task.id}')
