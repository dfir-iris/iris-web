#!/usr/bin/env python3
#
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

from datetime import datetime
from sqlalchemy import desc

from app import db
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import update_tasks_state
from app.models import CaseTasks
from app.models import TaskStatus
from app.models import User


def get_tasks_status():
    return TaskStatus.query.all()


def get_tasks(caseid):
    return CaseTasks.query.with_entities(
        CaseTasks.id.label("task_id"),
        CaseTasks.task_title,
        CaseTasks.task_description,
        CaseTasks.task_open_date,
        CaseTasks.task_tags,
        User.name.label('assignee_name'),
        CaseTasks.task_assignee_id,
        CaseTasks.task_status_id,
        TaskStatus.status_name,
        TaskStatus.status_bscolor
    ).filter(
        CaseTasks.task_case_id == caseid
    ).join(
        CaseTasks.user_assigned, CaseTasks.status
    ).order_by(
        desc(TaskStatus.status_name)
    ).all()


def get_task(task_id, caseid):
    return CaseTasks.query.filter(CaseTasks.id == task_id, CaseTasks.task_case_id == caseid).first()


def update_task_status(task_status, task_id, caseid):
    task = get_task(task_id, caseid)
    if task:
        try:
            task.task_status_id = task_status

            update_tasks_state(caseid=caseid)
            db.session.commit()
            return True

        except:
            return False
    else:
        return False


def add_task(task, user_id, caseid):

    now = datetime.now()
    task.task_case_id = caseid
    task.task_userid_open = user_id
    task.task_userid_update = user_id
    task.task_open_date = now
    task.task_last_update = now

    task.custom_attributes = task.custom_attributes if task.custom_attributes else get_default_custom_attributes('task')

    update_task_status(task.task_status_id, task.id, caseid)

    db.session.add(task)

    update_tasks_state(caseid=caseid)
    db.session.commit()

    return task
