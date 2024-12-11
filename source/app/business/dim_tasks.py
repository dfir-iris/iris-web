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


def dim_tasks_get(task_identifier):
    task = celery.AsyncResult(task_identifier)

    try:
        tinfo = task.info
    except AttributeError:
        # Legacy task
        return {
            'Danger': 'This task was executed in a previous version of IRIS and the status cannot be read anymore.',
            'Note': 'All the data readable by the current IRIS version is displayed in the table.',
            'Additional information': 'The results of this tasks were stored in a pickled Class which does not exists '
                                      'anymore in current IRIS version.'
        }

    task_info = {
        'Task ID': task_identifier,
        'Task finished on': task.date_done,
        'Task state': task.state.lower(),
        'Engine': task.name if task.name else 'No engine. Unrecoverable shadow failure'}

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
        task_info['User'] = 'Shadow Iris'
        task_info['Logs'] = ['Task did not returned a valid IIStatus object']

    if task_meta.get('traceback'):
        task_info['Traceback'] = task.traceback

    task_info['Success'] = 'Success' if success else 'Failure'

    return task_info
