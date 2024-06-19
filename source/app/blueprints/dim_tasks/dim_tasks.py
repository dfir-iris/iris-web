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

import json
import os
import pickle
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import url_for
from flask_wtf import FlaskForm
from sqlalchemy import desc

import app
from app.models import CeleryTaskMeta
from app.models import IrisHook
from app.models import IrisModule
from app.models import IrisModuleHook
from app.models.authorization import CaseAccessLevel
from app.models.authorization import Permissions
from app.util import ac_api_requires
from app.util import ac_case_requires
from app.util import ac_requires
from app.util import response_error
from app.util import response_success
from iris_interface.IrisInterfaceStatus import IIStatus

dim_tasks_blueprint = Blueprint(
    'dim_tasks',
    __name__,
    template_folder='templates'
)

basedir = os.path.abspath(os.path.dirname(app.__file__))


@dim_tasks_blueprint.route('/dim/tasks', methods=['GET'])
@ac_requires(Permissions.standard_user)
def dim_index(caseid: int, url_redir):
    if url_redir:
        return redirect(url_for('dim.dim_index', cid=caseid))

    form = FlaskForm()

    return render_template('dim_tasks.html', form=form)


@dim_tasks_blueprint.route('/dim/hooks/options/<hook_type>/list', methods=['GET'])
@ac_api_requires()
def list_dim_hook_options_ioc(hook_type):
    mods_options = (IrisModuleHook.query.with_entities(
        IrisModuleHook.manual_hook_ui_name,
        IrisHook.hook_name,
        IrisModule.module_name
    ).filter(
        IrisHook.hook_name == f"on_manual_trigger_{hook_type}",
        IrisModule.is_active == True
    )
    .join(IrisHook, IrisHook.id == IrisModuleHook.hook_id)
    .join(IrisModule, IrisModule.id == IrisModuleHook.module_id)
    .all())

    data = [options._asdict() for options in mods_options]

    return response_success("", data=data)


@dim_tasks_blueprint.route('/dim/tasks/list/<int:count>', methods=['GET'])
@ac_api_requires()
def list_dim_tasks(count):
    tasks = CeleryTaskMeta.query.filter(
        ~ CeleryTaskMeta.name.like('app.iris_engine.updater.updater.%')
    ).order_by(desc(CeleryTaskMeta.date_done)).limit(count).all()

    data = []

    for row in tasks:

        tkp = {}
        tkp['state'] = row.status
        tkp['case'] = "Unknown"
        tkp['module'] = row.name
        tkp['task_id'] = row.task_id
        tkp['date_done'] = row.date_done
        tkp['user'] = "Unknown"

        try:
            tinfo = row.result
        except AttributeError:
            # Legacy task
            data.append(tkp)
            continue

        if row.name is not None and 'task_hook_wrapper' in row.name:
            task_name = f"{row.kwargs}::{row.kwargs}"
        else:
            task_name = row.name

        user = None
        case_name = None
        if row.kwargs and row.kwargs != b'{}':
            kwargs = json.loads(row.kwargs.decode('utf-8'))
            if kwargs:
                user = kwargs.get('init_user')
                case_name = f"Case #{kwargs.get('caseid')}"
                task_name = f"{kwargs.get('module_name')}::{kwargs.get('hook_name')}"

        try:
            result = pickle.loads(row.result)
        except:
            result = None

        if isinstance(result, IIStatus):
            try:
                success = result.is_success()
            except:
                success = None
        else:
            success = None

        tkp['state'] = "success" if success else str(row.result)
        tkp['user'] = user if user else "Shadow Iris"
        tkp['module'] = task_name
        tkp['case'] = case_name if case_name else ""

        data.append(tkp)

    return response_success("", data=data)


@dim_tasks_blueprint.route('/dim/tasks/status/<task_id>', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def task_status(task_id, caseid, url_redir):
    if url_redir:
        return response_error("Invalid request")

    task = app.celery.AsyncResult(task_id)

    try:
        tinfo = task.info
    except AttributeError:
        # Legacy task
        task_info = {}
        task_info['Danger'] = 'This task was executed in a previous version of IRIS and the status cannot be read ' \
                              'anymore.'
        task_info['Note'] = 'All the data readable by the current IRIS version is displayed in ' \
                            'the table.'
        task_info['Additional information'] = 'The results of this tasks were stored in a pickled Class which does' \
                                              ' not exists anymore in current IRIS version.'
        return render_template("modal_task_info.html", data=task_info, task_id=task.id)

    task_info = {}
    task_info['Task ID'] = task_id
    task_info['Task finished on'] = task.date_done
    task_info['Task state']: task.state.lower()
    task_info['Engine']: task.name if task.name else "No engine. Unrecoverable shadow failure"

    task_meta = task._get_task_meta()

    if task_meta.get('name') \
            and ('task_hook_wrapper' in task_meta.get('name') or 'pipeline_dispatcher' in task_meta.get('name')):
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
        task_info['Logs'] = ['Task did not returned a valid IIStatus object']

    if task_meta.get('traceback'):
        task_info['Traceback'] = task.traceback

    task_info['Success'] = "Success" if success else "Failure"

    return render_template("modal_task_info.html", data=task_info, task_id=task.id)
