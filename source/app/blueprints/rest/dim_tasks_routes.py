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

from flask import Blueprint
from flask import request
import json
import pickle
from sqlalchemy import desc

from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.models.models import CeleryTaskMeta
from app.models.models import IrisHook
from app.models.models import IrisModule
from app.models.models import IrisModuleHook
from app.models.models import CaseAssets
from app.models.models import CaseReceivedFile
from app.models.models import CaseTasks
from app.models.cases import Cases
from app.models.cases import CasesEvent
from app.models.models import GlobalTasks
from app.models.models import Ioc
from app.models.models import Notes
from app.models.alerts import Alert
from app.models.authorization import CaseAccessLevel
from app.blueprints.access_controls import ac_requires_case_identifier
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success
from iris_interface.IrisInterfaceStatus import IIStatus

dim_tasks_rest_blueprint = Blueprint('dim_tasks_rest', __name__)


@dim_tasks_rest_blueprint.route('/dim/hooks/call', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def dim_hooks_call(caseid):
    logs = []
    js_data = request.json

    if not js_data:
        return response_error('Invalid data')

    hook_name = js_data.get('hook_name')
    if not hook_name:
        return response_error('Missing hook_name')

    hook_ui_name = js_data.get('hook_ui_name')

    targets = js_data.get('targets')
    if not targets:
        return response_error('Missing targets')

    data_type = js_data.get('type')
    if not data_type:
        return response_error('Missing data type')

    module_name = js_data.get('module_name')

    index = 0
    obj_targets = []
    for target in js_data.get('targets'):
        if type(target) is str:
            try:
                target = int(target)
            except ValueError:
                return response_error('Invalid target')

        elif type(target) != int:
            return response_error('Invalid target')

        if data_type == 'ioc':
            obj = Ioc.query.filter(Ioc.ioc_id == target).first()

        elif data_type == "case":
            obj = Cases.query.filter(Cases.case_id == caseid).first()

        elif data_type == "asset":
            obj = CaseAssets.query.filter(
                CaseAssets.asset_id == target,
                CaseAssets.case_id == caseid
            ).first()

        elif data_type == "note":
            obj = Notes.query.filter(
                Notes.note_id == target,
                Notes.note_case_id == caseid
            ).first()

        elif data_type == "event":
            obj = CasesEvent.query.filter(
                CasesEvent.event_id == target,
                CasesEvent.case_id == caseid
            ).first()

        elif data_type == "task":
            obj = CaseTasks.query.filter(
                CaseTasks.id == target,
                CaseTasks.task_case_id == caseid
            ).first()

        elif data_type == "evidence":
            obj = CaseReceivedFile.query.filter(
                CaseReceivedFile.id == target,
                CaseReceivedFile.case_id == caseid
            ).first()

        elif data_type == "global_task":
            obj = GlobalTasks.query.filter(
                GlobalTasks.id == target
            ).first()

        elif data_type == 'alert':
            obj = Alert.query.filter(
                Alert.alert_id == target
            ).first()

        else:
            logs.append(f'Data type {data_type} not supported')
            continue

        if not obj:
            logs.append(f'Object ID {target} not found')
            continue
        obj_targets.append(obj)

        # Call to queue task
        index += 1

    if len(obj_targets) > 0:
        call_modules_hook(hook_name=hook_name, hook_ui_name=hook_ui_name, data=obj_targets,
                          caseid=caseid, module_name=module_name)

    if len(logs) > 0:
        return response_error(f"Errors encountered during processing of data. Queued task with {index} objects",
                              data=logs)

    return response_success(f'Queued task with {index} objects')


@dim_tasks_rest_blueprint.route('/dim/hooks/options/<hook_type>/list', methods=['GET'])
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


@dim_tasks_rest_blueprint.route('/dim/tasks/list/<int:count>', methods=['GET'])
@ac_api_requires()
def list_dim_tasks(count):
    tasks = CeleryTaskMeta.query.filter(
        ~ CeleryTaskMeta.name.like('app.iris_engine.updater.updater.%')
    ).order_by(desc(CeleryTaskMeta.date_done)).limit(count).all()

    data = []

    for row in tasks:

        tkp = {'state': row.status, 'case': "Unknown", 'module': row.name, 'task_id': row.task_id, 'date_done': row.date_done, 'user': "Unknown"}

        try:
            _ = row.result
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
