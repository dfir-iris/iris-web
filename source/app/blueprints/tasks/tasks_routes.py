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

    tinfo = None
    try:
        tinfo = task.info.get_data()

    except:
        log.warning("{} does not respects task return convention".format(task.name))
        pass
    success = False
    logs = []
    user = "Shadow Iris"
    case_name = ""
    initial = 0

    if tinfo:
        success = tinfo.success
        logs = tinfo.logs
        user = tinfo.user
        case_name = tinfo.case_name
        initial = tinfo.initial

    rsp = {
        'state': task.state.lower(),
        'success': success,
        'name': task.name if task.name else "No engine. Unrecoverable shadow failure",
        'traceback': task.traceback,
        'args': task.args,
        'date': task.date_done,
        'user': user,
        'logs': logs,
        'case_name': case_name,
        'initial': initial,
        'status': "Success" if success else "Failure"
    }

    return render_template("modal_task_info.html", data=rsp, task_id=task.id)


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

            tinfo = None
            try:

                tinfo = task.info.get_data()

            except:
                log.warning("{} does not respects task return convention".format(task.name))
                pass

            success = None
            user = "Shadow Iris"
            case_name = ""
            task_name, = task.name if task.name else "No engine. Unrecoverable shadow failure",

            if tinfo:
                success = tinfo.success
                user = tinfo.user
                case_name = tinfo.case_name

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
