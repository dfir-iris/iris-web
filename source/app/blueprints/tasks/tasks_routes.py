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

# IMPORTS ------------------------------------------------

import logging
import time
from os import environ
from sys import platform

from flask import Blueprint
from flask import render_template
from sqlalchemy import desc

import app
from app.models.models import CeleryTaskMeta
from app.util import response_success, response_error, login_required, api_login_required
from iris_interface.IrisInterfaceStatus import IIStatus, IITaskStatus

log = logging.getLogger('iris')

environ['TZ'] = 'Europe/London'
if platform == "linux":
    time.tzset()

# VARS ----------------------------------------------------
tasks_blueprint = Blueprint('tasks',
                            __name__,
                            template_folder='templates')


# CONTENT -------------------------------------------------
@tasks_blueprint.route('/tasks/status/human/<task_id>', methods=['GET', 'POST'])
@login_required
def task_status(task_id, caseid, url_redir):
    if url_redir:
        return response_error("Invalid request")

    task = app.celery.AsyncResult(task_id)

    task_info = {}
    task_info['Task ID'] = task_id
    task_info['Task Done'] = task.date_done
    task_info['Task State']: task.state.lower()
    task_info['Engine']: task.name if task.name else "No engine. Unrecoverable shadow failure"

    task_meta = task._get_task_meta()

    if 'task_hook_wrapper' in task_meta.get('name'):
        task_info['Module Name'] = task_meta.get('kwargs').get('module_name')
        task_info['Hook Name'] = task_meta.get('kwargs').get('hook_name')
        task_info['User'] = task_meta.get('kwargs').get('init_user')
        task_info['Case ID'] = task_meta.get('kwargs').get('caseid')

    if isinstance(task.info, IIStatus) and task.info.get_data():
        # tinfo = task.info.get_data()
        success = task.info.is_success()
        # task_info['User'] = tinfo.user
        # task_info['Case Name'] = tinfo.case_name
        task_info['Logs'] = task.info.get_logs()

    else:
        success = None
        task_info['User'] = "Shadow Iris"
        task_info['Logs'] = ['Task did not returned an IIStatus object']

    if task_meta.get('traceback'):
        task_info['Traceback'] = task.traceback

    task_info['Success'] = "Success" if success else "Failure"

    return render_template("modal_task_info.html", data=task_info, task_id=task.id)


@tasks_blueprint.route("/tasks", methods=['GET'])
@api_login_required
def tasks_list(caseid):
    tasks = CeleryTaskMeta.query.with_entities(
        CeleryTaskMeta.task_id,
        CeleryTaskMeta.date_done,
    ).order_by(desc(CeleryTaskMeta.date_done)).limit(10).all()

    data = []

    for row in tasks:
        if row.task_id:
            task = app.celery.AsyncResult(row.task_id)

            if isinstance(task.info, IIStatus) and task.info.get_data():
                success = task.info.is_success()

            else:
                success = None
                user = "Shadow Iris"
                case_name = ""

            task_name = task.name if task.name else "No engine. Unrecoverable shadow failure"
            if 'task_hook_wrapper' in task_name:
                task_meta = task._get_task_meta()
                task_name = f"{task_meta.get('kwargs').get('module_name')}::{task_meta.get('kwargs').get('hook_name')}"
                user = task_meta.get('kwargs').get('init_user')
                case_name = f"for case #{task_meta.get('kwargs').get('caseid')}"

            row = row._asdict()
            status = "Success" if success else "Failure"
            row['state'] = "success" if success else "failure"

            if task.state == 'PROGRESS':
                status = 'Running'
                row['state'] = 'progress'

            row['human_data'] = "{user} - {task} {case_name} - {status}".format(
                user=user,
                task=task_name,
                status=status,
                case_name="for {}".format(case_name) if case_name else ""
            )

            row['date'] = task.date_done if task.date_done is not None else "Now"

            data.append(row)

    return response_success("", data=data)
