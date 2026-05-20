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

import json
import pickle

from app import celery
from app.datamgmt.asynchronous_tasks import search_asynchronous_tasks
from iris_interface.IrisInterfaceStatus import IIStatus


def _get_engine_name(task):
    if not task.name:
        return 'No engine. Unrecoverable shadow failure'
    return task.name


def _get_success(task_result: IIStatus):
    if task_result.is_success():
        return 'Success'
    return 'Failure'


def _dim_tasks_is_legacy(task):
    try:
        _ = task.date_done
        return False
    except AttributeError:
        return True


def dim_tasks_get(task_identifier):
    task = celery.AsyncResult(task_identifier)
    if _dim_tasks_is_legacy(task):
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


def asynchronous_tasks_search(count):
    tasks = search_asynchronous_tasks(count)

    data = []

    for row in tasks:

        tkp = {'state': row.status, 'case': 'Unknown', 'module': row.name, 'task_id': row.task_id,
               'date_done': row.date_done, 'user': 'Unknown'}

        try:
            _ = row.result
        except AttributeError:
            # Legacy task
            data.append(tkp)
            continue

        if row.name is not None and 'task_hook_wrapper' in row.name:
            task_name = f'{row.kwargs}::{row.kwargs}'
        else:
            task_name = row.name

        user = None
        case_name = None
        if row.kwargs and row.kwargs != b'{}':
            kwargs = json.loads(row.kwargs.decode('utf-8'))
            if kwargs:
                user = kwargs.get('init_user')
                case_identifier = kwargs.get('caseid')
                case_name = f'Case #{case_identifier}'
                module_name = kwargs.get('module_name')
                hook_name = kwargs.get('hook_name')
                task_name = f'{module_name}::{hook_name}'

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

        tkp['state'] = 'success' if success else str(row.result)
        tkp['user'] = user if user else 'Shadow Iris'
        tkp['module'] = task_name
        tkp['case'] = case_name if case_name else ''

        data.append(tkp)
    return data
