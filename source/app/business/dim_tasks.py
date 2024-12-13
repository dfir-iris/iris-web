#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

from app import celery
from iris_interface.IrisInterfaceStatus import IIStatus


def _get_engine_name(task):
    if not task.name:
        return 'No engine. Unrecoverable shadow failure'
    return task.name

def _get_success(task_result: IIStatus):
    if task_result.is_success():
        return 'Success'
    else:
        return 'Failure'

def dim_tasks_is_legacy(task):
    try:
        _ = task.info
        return False
    except AttributeError:
        return True

def dim_tasks_get(task_identifier):
    task = celery.AsyncResult(task_identifier)
    if dim_tasks_is_legacy(task):
        return {
            'Danger': 'This task was executed in a previous version of IRIS and the status cannot be read anymore.',
            'Note': 'All the data readable by the current IRIS version is displayed in the table.',
            'Additional information': 'The results of this tasks were stored in a pickled Class which does not exists '
                                      'anymore in current IRIS version.'
        }

    engine_name = _get_engine_name(task)
    user = None
    module_name = None
    hook_name = None
    case_identifier = None
    if task.name and ('task_hook_wrapper' in task.name or 'pipeline_dispatcher' in task.name):
        module_name = task.kwargs.get('module_name')
        hook_name = task.kwargs.get('hook_name')
        user = task.kwargs.get('init_user')
        case_identifier = task.kwargs.get('caseid')

    if isinstance(task.info, IIStatus):
        success = _get_success(task.info)
        logs = task.info.get_logs()
    else:
        success = 'Failure'
        user = 'Shadow Iris'
        logs = ['Task did not returned a valid IIStatus object']

    return {
        'Task ID': task_identifier,
        'Task finished on': task.date_done,
        'Task state': task.state.lower(),
        'Engine': engine_name,
        'Module name': module_name,
        'Hook name': hook_name,
        'Case ID': case_identifier,
        'Success': success,
        'User': user,
        'Logs': logs,
        'Traceback': task.traceback
    }
