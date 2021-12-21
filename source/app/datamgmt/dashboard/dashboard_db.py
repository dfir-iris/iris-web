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

from sqlalchemy import desc

from app import db
from app.models import GlobalTasks, User

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