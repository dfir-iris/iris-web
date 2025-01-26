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

import os
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import url_for
from flask_wtf import FlaskForm

import app
from app.models.authorization import CaseAccessLevel
from app.models.authorization import Permissions
from app.blueprints.access_controls import ac_case_requires, ac_requires
from app.blueprints.responses import response_error
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
        task_info = {
            'Danger': 'This task was executed in a previous version of IRIS and the status cannot be read anymore.',
            'Note': 'All the data readable by the current IRIS version is displayed in the table.',
            'Additional information': 'The results of this tasks were stored in a pickled Class which does not exists '
                                      'anymore in current IRIS version.'
        }
        return render_template("modal_task_info.html", data=task_info, task_id=task.id)

    task_info = {
        'Task ID': task_id,
        'Task finished on': task.date_done,
        'Task state': task.state.lower(),
        'Engine': task.name if task.name else "No engine. Unrecoverable shadow failure"}

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
