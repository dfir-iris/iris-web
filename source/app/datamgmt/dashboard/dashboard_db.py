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

from sqlalchemy import desc, and_

from app import db
from app.models import GlobalTasks, User, Cases, CaseTasks

task_status = ['To do', 'In progress', 'On hold', 'Done', 'Canceled']


def list_global_tasks():
    ct = GlobalTasks.query.with_entities(
        GlobalTasks.id.label("task_id"),
        GlobalTasks.task_title,
        GlobalTasks.task_description,
        GlobalTasks.task_last_update,
        GlobalTasks.task_tags,
        User.name.label('user_name'),
        GlobalTasks.task_status
    ).join(
        GlobalTasks.user_assigned
    ).order_by(
        desc(GlobalTasks.task_status)
    ).all()
    output = [c._asdict() for c in ct]

    return output


def list_user_tasks():
    ct = CaseTasks.query.with_entities(
        CaseTasks.id.label("task_id"),
        CaseTasks.task_title,
        CaseTasks.task_description,
        CaseTasks.task_last_update,
        CaseTasks.task_tags,
        Cases.name.label('task_case'),
        CaseTasks.task_case_id.label('case_id'),
        CaseTasks.task_status
    ).join(
        CaseTasks.case
    ).order_by(
        desc(CaseTasks.task_status)
    ).filter(and_(
        CaseTasks.task_status != 'Done',
        CaseTasks.task_status != 'Canceled'
    )).all()
    output = [c._asdict() for c in ct]

    return output


def update_gtask_status(task_id, status):
    if task_id != 0:
        task = GlobalTasks.query.filter(
                GlobalTasks.id == task_id
        ).first()

        if task and status in task_status:
            task.task_status = status
            db.session.commit()

            return True

    return False


def update_utask_status(task_id, status, case_id):
    if task_id != 0:
        task = CaseTasks.query.filter(
                CaseTasks.id == task_id,
                CaseTasks.task_case_id == case_id
        ).first()

        if task and status in task_status:
            task.task_status = status
            db.session.commit()

            return task

    return None