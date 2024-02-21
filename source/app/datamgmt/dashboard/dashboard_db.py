#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
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
from flask_login import current_user
from sqlalchemy import and_
from sqlalchemy import desc

from app import db
from app.models import CaseTasks, TaskAssignee, ReviewStatus
from app.models import Cases
from app.models import GlobalTasks
from app.models import TaskStatus
from app.models.authorization import User


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


def get_tasks_status():
    return TaskStatus.query.all()


def list_user_reviews():
    ct = Cases.query.with_entities(
        Cases.case_id,
        Cases.name,
        ReviewStatus.status_name,
        ReviewStatus.id.label('status_id')
    ).join(
        Cases.review_status
    ).filter(
        Cases.reviewer_id == current_user.id,
        ReviewStatus.status_name != 'Reviewed',
        ReviewStatus.status_name != 'Not reviewed'
    ).all()

    return ct


def list_user_tasks():
    ct = CaseTasks.query.with_entities(
        CaseTasks.id.label("task_id"),
        CaseTasks.task_title,
        CaseTasks.task_description,
        CaseTasks.task_last_update,
        CaseTasks.task_tags,
        Cases.name.label('task_case'),
        CaseTasks.task_case_id.label('case_id'),
        CaseTasks.task_status_id,
        TaskStatus.status_name,
        TaskStatus.status_bscolor
    ).join(
        CaseTasks.case
    ).order_by(
        desc(TaskStatus.status_name)
    ).filter(and_(
        TaskStatus.status_name != 'Done',
        TaskStatus.status_name != 'Canceled'
    )).join(
        CaseTasks.status,
    ).filter(and_(
        TaskAssignee.task_id == CaseTasks.id,
        TaskAssignee.user_id == current_user.id
    )).all()

    return ct


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


def update_utask_status(task_id, status, case_id):
    if task_id != 0:
        task = CaseTasks.query.filter(
                CaseTasks.id == task_id,
                CaseTasks.task_case_id == case_id
        ).first()
        if task:
            try:
                task.task_status_id = status

                db.session.commit()
                return True

            except:
                pass

    return False


def get_task_status(task_status_id):
    ret = TaskStatus.query.filter(
        TaskStatus.id == task_status_id
    ).first()

    return ret


def list_user_cases(show_all=False):
    if show_all:
        return Cases.query.filter(
            Cases.owner_id == current_user.id
        ).all()

    return Cases.query.filter(
        Cases.owner_id == current_user.id,
        Cases.close_date == None
    ).all()


