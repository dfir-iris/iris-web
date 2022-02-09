#!/usr/bin/env python3
#
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
import json

import pickle

import os

from flask import Blueprint
from flask import render_template, url_for, redirect
from flask_wtf import FlaskForm
from iris_interface.IrisInterfaceStatus import IIStatus
from sqlalchemy import desc

import app
from app.datamgmt.activities.activities_db import get_all_user_activities
from app.models import CeleryTaskMeta
from app.util import response_success, login_required, api_login_required, response_error

dim_tasks_blueprint = Blueprint(
    'dim_tasks',
    __name__,
    template_folder='templates'
)

basedir = os.path.abspath(os.path.dirname(app.__file__))


# CONTENT ------------------------------------------------
@dim_tasks_blueprint.route('/dim/tasks', methods=['GET'])
@login_required
def dim_index(caseid: int, url_redir):
    if url_redir:
        return redirect(url_for('dim.dim_index', cid=caseid))

    form = FlaskForm()

    return render_template('dim_tasks.html', form=form)


@dim_tasks_blueprint.route('/dim/tasks/list', methods=['GET'])
@api_login_required
def list_dim_tasks(caseid):
    tasks = CeleryTaskMeta.query.with_entities(
        CeleryTaskMeta.task_id,
        CeleryTaskMeta.date_done
    ).order_by(desc(CeleryTaskMeta.date_done)).limit(200).all()

    data = []

    for row in tasks:
        task = app.celery.AsyncResult(row.task_id)

        task_name = task.name if task.name else "No engine. Unrecoverable shadow failure"
        if 'task_hook_wrapper' in task_name:
            task_name = f"{task.kwargs.get('module_name')}::{task.kwargs.get('hook_name')}"
        else:
            task_name = task.name

        if task.kwargs:
            user = task.kwargs.get('init_user')
            case_name = f"Case #{task.kwargs.get('caseid')}"
        else:
            user = "Shadow Iris"
            case_name = "Unknown"

        if isinstance(task.result, IIStatus):

            try:
                success = task.result.is_success()
            except:
                success = None

        else:
            success = None

        row = row._asdict()
        row['state'] = "success" if success else str(task.result)
        row['user'] = user

        row['module'] = task_name
        row['case'] = case_name if case_name else ""

        data.append(row)

    return response_success("", data=data)


@dim_tasks_blueprint.route('/dim/tasks/limited-list', methods=['GET'])
@api_login_required
def list_limited_dim_tasks(caseid):
    tasks = CeleryTaskMeta.query.with_entities(
        CeleryTaskMeta.task_id,
        CeleryTaskMeta.date_done
    ).order_by(desc(CeleryTaskMeta.date_done)).limit(20).all()

    data = []

    for row in tasks:
        task = app.celery.AsyncResult(row.task_id)

        task_name = task.name if task.name else "No engine. Unrecoverable shadow failure"
        if 'task_hook_wrapper' in task_name:
            task_name = f"{task.kwargs.get('module_name')}::{task.kwargs.get('hook_name')}"
        else:
            task_name = task.name

        if task.kwargs:
            user = task.kwargs.get('init_user')
            case_name = f"Case #{task.kwargs.get('caseid')}"
        else:
            user = "Shadow Iris"
            case_name = "Unknown"

        if isinstance(task.result, IIStatus):

            try:
                success = task.result.is_success()
            except:
                success = None

        else:
            success = None

        row = row._asdict()
        row['state'] = "success" if success else str(task.result)
        row['user'] = user

        row['module'] = task_name
        row['case'] = case_name if case_name else ""

        data.append(row)

    return response_success("", data=data)


@dim_tasks_blueprint.route('/dim/tasks/status/<task_id>', methods=['GET'])
@login_required
def task_status(task_id, caseid, url_redir):
    if url_redir:
        return response_error("Invalid request")

    task = app.celery.AsyncResult(task_id)

    task_info = {}
    task_info['Task ID'] = task_id
    task_info['Task finish on'] = task.date_done
    task_info['Task state']: task.state.lower()
    task_info['Engine']: task.name if task.name else "No engine. Unrecoverable shadow failure"

    task_meta = task._get_task_meta()

    if 'task_hook_wrapper' in task_meta.get('name'):
        task_info['Module name'] = task_meta.get('kwargs').get('module_name')
        task_info['Hook name'] = task_meta.get('kwargs').get('hook_name')
        task_info['User'] = task_meta.get('kwargs').get('init_user')
        task_info['Case ID'] = task_meta.get('kwargs').get('caseid')

    if isinstance(task.info, IIStatus):
        success = task.info.is_success()
        task_info['Logs'] = task.info.get_logs()

    else:
        success = None
        task_info['User'] = "Shadow Iris"
        task_info['Logs'] = ['Task did not returned an IIStatus object']

    if task_meta.get('traceback'):
        task_info['Traceback'] = task.traceback

    task_info['Success'] = "Success" if success else "Failure"

    return render_template("modal_task_info.html", data=task_info, task_id=task.id)

