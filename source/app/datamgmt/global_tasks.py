#  IRIS Source Code
#  Copyright (C) ${current_year} - DFIR-IRIS
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

from sqlalchemy import desc
from flask_sqlalchemy.pagination import Pagination

from app.db import db
from app.models.authorization import User
from app.models.models import GlobalTasks
from app.models.models import TaskStatus
from app.models.pagination_parameters import PaginationParameters
from app.datamgmt.filtering import paginate


def delete_global_task(task: GlobalTasks):
    GlobalTasks.query.filter(GlobalTasks.id == task.id).delete()
    db.session.commit()


def update_global_task():
    db.session.commit()


def filter_global_tasks(pagination_parameters: PaginationParameters) -> Pagination:
    query = GlobalTasks.query

    return paginate(GlobalTasks, pagination_parameters, query)


def list_global_tasks():
    ct = GlobalTasks.query.with_entities(
        GlobalTasks.id.label("task_id"),
        GlobalTasks.task_uuid,
        GlobalTasks.task_title,
        GlobalTasks.task_description,
        GlobalTasks.task_last_update,
        GlobalTasks.task_tags,
        User.name.label('user_name'),
        GlobalTasks.task_assignee_id,
        GlobalTasks.task_status_id,
        TaskStatus.status_name,
        TaskStatus.status_bscolor
    ).join(
        GlobalTasks.user_assigned
    ).order_by(
        desc(TaskStatus.status_name)
    ).join(
        GlobalTasks.status
    ).all()

    return ct


def get_global_task(task_id):
    ct = GlobalTasks.query.with_entities(
        GlobalTasks.id.label("task_id"),
        GlobalTasks.task_uuid,
        GlobalTasks.task_title,
        GlobalTasks.task_description,
        GlobalTasks.task_last_update,
        GlobalTasks.task_tags,
        User.name.label('user_name'),
        GlobalTasks.task_assignee_id,
        GlobalTasks.task_status_id,
        TaskStatus.status_name,
        TaskStatus.status_bscolor
    ).filter(
        GlobalTasks.id == task_id
    ).join(
        GlobalTasks.user_assigned
    ).join(
        GlobalTasks.status
    ).order_by(
        desc(TaskStatus.status_name)
    ).first()

    return ct


def get_global_task_by_identifier(identifier):
    return GlobalTasks.query.filter(
        GlobalTasks.id == identifier
    ).first()


def update_gtask_status(task_id, status):
    if task_id != 0:
        task = GlobalTasks.query.filter(
                GlobalTasks.id == task_id
        ).first()

        try:
            task.task_status_id = status
            db.session.commit()
            return task
        except:
            pass

    return None
