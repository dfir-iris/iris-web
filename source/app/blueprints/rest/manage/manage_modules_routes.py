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
import logging as log
import traceback
from flask import Blueprint
from flask import request

from app import app
from app.datamgmt.iris_engine.modules_db import delete_module_from_id
from app.datamgmt.iris_engine.modules_db import parse_module_parameter
from app.datamgmt.iris_engine.modules_db import get_module_config_from_id
from app.datamgmt.iris_engine.modules_db import iris_module_disable_by_id
from app.datamgmt.iris_engine.modules_db import iris_module_enable_by_id
from app.datamgmt.iris_engine.modules_db import iris_module_name_from_id
from app.datamgmt.iris_engine.modules_db import iris_module_save_parameter
from app.datamgmt.iris_engine.modules_db import iris_modules_list
from app.datamgmt.iris_engine.modules_db import module_list_hooks_view
from app.iris_engine.module_handler.module_handler import check_module_health
from app.iris_engine.module_handler.module_handler import instantiate_module_from_name
from app.iris_engine.module_handler.module_handler import iris_update_hooks
from app.iris_engine.module_handler.module_handler import register_module
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success
from app.schema.marshables import IrisModuleSchema

manage_modules_rest_blueprint = Blueprint('manage_module_rest', __name__)


@manage_modules_rest_blueprint.route('/manage/modules/list', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def manage_modules_list():
    output = iris_modules_list()

    return response_success('', data=output)


@manage_modules_rest_blueprint.route('/manage/modules/add', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def add_module():
    if request.json is None:
        return response_error('Invalid request')

    module_name = request.json.get('module_name')

    # Try to import the module
    try:
        # Try to instantiate the module
        log.info(f'Trying to add module {module_name}')
        class_, logs = instantiate_module_from_name(module_name)

        if not class_:
            return response_error(f"Cannot import module. {logs}")

        # Check the health of the module
        is_ready, logs = check_module_health(class_)

        if not is_ready:
            return response_error("Cannot import module. Health check didn't pass. Please check logs below", data=logs)

        # Registers into Iris DB for further calls
        module, message = register_module(module_name)
        if module is None:
            track_activity(f"addition of IRIS module {module_name} was attempted and failed", ctx_less=True)
            return response_error(f'Unable to register module: {message}')

        track_activity(f"IRIS module {module_name} was added", ctx_less=True)
        module_schema = IrisModuleSchema()
        return response_success(message, data=module_schema.dump(module))

    except Exception as e:
        traceback.print_exc()
        return response_error(e.__str__())


@manage_modules_rest_blueprint.route('/manage/modules/set-parameter/<param_name>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def update_module_param(param_name):
    if request.json is None:
        return response_error('Invalid request')

    mod_config, mod_id, mod_name, mod_iname, parameter = parse_module_parameter(param_name)

    if mod_config is None:
        return response_error('Invalid parameter')

    parameter_value = request.json.get('parameter_value')

    if iris_module_save_parameter(mod_id, mod_config, parameter['param_name'], parameter_value):
        track_activity(f"parameter {parameter['param_name']} of mod ({mod_name})  #{mod_id} was updated",
                       ctx_less=True)

        success, logs = iris_update_hooks(mod_iname, mod_id)
        if not success:
            return response_error("Unable to update hooks", data=logs)

        return response_success("Saved", logs)

    return response_error('Malformed request')


@manage_modules_rest_blueprint.route('/manage/modules/enable/<int:mod_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def enable_module(mod_id):
    module_name = iris_module_name_from_id(mod_id)
    if module_name is None:
        return response_error('Invalid module ID')

    if not iris_module_enable_by_id(mod_id):
        return response_error('Unable to enable module')

    success, logs = iris_update_hooks(module_name, mod_id)
    if not success:
        return response_error("Unable to update hooks when enabling module", data=logs)

    track_activity(f"IRIS module ({module_name}) #{mod_id} enabled", ctx_less=True)

    return response_success('Module enabled', data=logs)


@manage_modules_rest_blueprint.route('/manage/modules/disable/<int:module_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def disable_module(module_id):
    if iris_module_disable_by_id(module_id):
        track_activity(f"IRIS module #{module_id} disabled", ctx_less=True)
        return response_success('Module disabled')

    return response_error('Unable to disable module')


@manage_modules_rest_blueprint.route('/manage/modules/remove/<int:module_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def view_delete_module(module_id):
    try:

        delete_module_from_id(module_id=module_id)
        track_activity(f"IRIS module #{module_id} deleted", ctx_less=True)
        return response_success("Deleted")

    except Exception as e:
        log.error(e.__str__())
        return response_error(f"Cannot delete module. Error {e.__str__()}")


@manage_modules_rest_blueprint.route('/manage/modules/export-config/<int:module_id>', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def export_mod_config(module_id):
    mod_config, mod_name, _ = get_module_config_from_id(module_id)
    if mod_name:
        data = {
            "module_name": mod_name,
            "module_configuration": mod_config
        }
        return response_success(data=data)

    return response_error(f"Module ID {module_id} not found")


@manage_modules_rest_blueprint.route('/manage/modules/import-config/<int:module_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def import_mod_config(module_id):
    mod_config, _, _ = get_module_config_from_id(module_id)
    logs = []
    parameters_data = request.get_json().get('module_configuration')

    if type(parameters_data) is not list:
        try:
            parameters = json.loads(parameters_data)
        except Exception as _:
            return response_error('Invalid data', data="Not a JSON file")
    else:
        parameters = parameters_data

    for param in parameters:
        param_name = param.get('param_name')
        parameter_value = param.get('value')
        if not iris_module_save_parameter(module_id, mod_config, param_name, parameter_value):
            logs.append(f'Unable to save parameter {param_name}')

    track_activity(f"parameters of mod #{module_id} were updated from config file", ctx_less=True)

    if len(logs) == 0:
        msg = "Successfully imported data."
    else:
        msg = "Configuration is partially imported, we got errors with the followings:\n- " + "\n- ".join(logs)

    return response_success(msg)


@manage_modules_rest_blueprint.route('/manage/modules/hooks/list', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def view_modules_hook():
    output = module_list_hooks_view()
    data = [item._asdict() for item in output]

    return response_success('', data=data)


# TODO is this endpoint still useful?
@manage_modules_rest_blueprint.route('/sitemap', methods=['GET'])
@ac_api_requires()
def site_map():
    links = []
    for rule in app.url_map.iter_rules():
        methods = [m for m in rule.methods if m != 'OPTIONS' and m != 'HEAD']
        links.append((','.join(methods), str(rule), rule.endpoint))

    return response_success('', data=links)
