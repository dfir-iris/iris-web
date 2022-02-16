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
import base64
import logging as log
import traceback

from flask import Blueprint, request, redirect, url_for
from flask import render_template
from flask_wtf import FlaskForm

from app import app
from app.datamgmt.iris_engine.modules_db import iris_modules_list, get_module_from_id, delete_module_from_id, \
    get_module_config_from_id, is_mod_configured, iris_module_save_parameter, iris_module_enable_by_id, \
    iris_module_disable_by_id, module_list_hooks_view
from app.forms import AddModuleForm, UpdateModuleParameterForm
from app.iris_engine.module_handler.module_handler import check_module_health, register_module, \
    instantiate_module_from_name
from app.iris_engine.utils.tracker import track_activity
from app.util import admin_required, response_error, response_success, api_admin_required, login_required

manage_modules_blueprint = Blueprint(
    'manage_module',
    __name__,
    template_folder='templates'
)


def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)


# CONTENT ------------------------------------------------
@manage_modules_blueprint.route("/sitemap")
@login_required
def site_map(caseid, url_redir):
    links = []
    for rule in app.url_map.iter_rules():
        # Filter out rules we can't navigate to in a browser
        # and rules that require parameters
        if "GET" in rule.methods and has_no_empty_params(rule):
            url = url_for(rule.endpoint, **(rule.defaults or {}))
            links.append((url, rule.endpoint))

    return response_error('', data=links)


@manage_modules_blueprint.route('/manage/modules', methods=['GET'])
@admin_required
def manage_modules_index(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_module.manage_modules_index', cid=caseid))

    form = FlaskForm()

    return render_template("manage_modules.html", form=form)


@manage_modules_blueprint.route('/manage/modules/list', methods=['GET'])
@api_admin_required
def manage_modules_list(caseid):
    output = iris_modules_list()

    return response_success('', data=output)


@manage_modules_blueprint.route('/manage/modules/add', methods=['GET', 'POST'])
@admin_required
def add_module(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_modules.add_module', cid=caseid))

    module = None
    form = AddModuleForm()

    if form.is_submitted():
        module_name = request.form.get('module_name', type=str)

        # Try to import the module
        try:
            # Try to instantiate the module
            log.info('Trying to add module {}'.format(module_name))
            class_ = instantiate_module_from_name(module_name)

            # Check the health of the module
            is_ready, logs = check_module_health(class_)

            if is_ready:
                # Registers into Iris DB for further calls
                success, logs = register_module(module_name)
                if success:
                    track_activity("IRIS module {} was added".format(module_name), caseid=caseid, ctx_less=True)
                    return response_success("", data=logs)
                else:
                    track_activity("addition of IRIS module {} was attempted".format(module_name),
                                   caseid=caseid, ctx_less=True)
                    return response_error("Unable to register module", data=logs)
            else:
                return response_error("Cannot import module. Health check didn't pass. Please check logs below", data=logs)

        except Exception as e:
            traceback.print_exc()
            return response_error(e.__str__())

    return render_template("modal_add_module.html", form=form, module=module)


@manage_modules_blueprint.route('/manage/modules/update_param/<param_name>', methods=['GET', 'POST'])
@api_admin_required
def update_module_param(param_name, caseid):
    try:

        param = base64.b64decode(param_name).decode('utf-8')
        mod_id = param.split('##')[0]
        param_name = param.split('##')[1]

    except Exception as e:
        log.error(e.__str__())
        return response_error('Malformed request', status=400)

    mod_config, mod_name = get_module_config_from_id(mod_id)
    form = UpdateModuleParameterForm()
    parameter = None
    for param in mod_config:
        if param_name == param['param_name']:
            parameter = param
            break

    if not parameter:
        return response_error('Malformed request', status=400)

    if request.method == 'POST':
        parameter_value = request.json.get('param_value')
        if iris_module_save_parameter(mod_id, mod_config, param_name, parameter_value):
            track_activity("parameter {} of mod #{} was updated".format(param_name, mod_id),
                           caseid=caseid, ctx_less=True)
            return response_success("Saved")
        else:
            return response_error('Malformed request', status=400)
    else:
        return render_template("modal_update_parameter.html", parameter=parameter, mod_name=mod_name, mod_id=mod_id, form=form)


@manage_modules_blueprint.route('/manage/modules/update/<int:id>', methods=['GET', 'POST'])
@api_admin_required
def view_module(id, caseid):
    form = AddModuleForm()

    if id:
        module = get_module_from_id(id)
        config = module.module_config

        is_configured = is_mod_configured(config)
        return render_template("modal_module_info.html", form=form, data=module,
                               config=config, is_configured=is_configured)

    return response_error('Malformed request', status=400)


@manage_modules_blueprint.route('/manage/modules/enable/<int:id>', methods=['GET', 'POST'])
@api_admin_required
def enable_module(id, caseid):
    if id:
        if iris_module_enable_by_id(id):
            track_activity("IRIS module #{} enabled".format(id),
                           caseid=caseid, ctx_less=True)
            return response_success('')
        else:
            return response_error('Unable to enable module')

    return response_error('Malformed request', status=400)


@manage_modules_blueprint.route('/manage/modules/disable/<int:id>', methods=['GET', 'POST'])
@api_admin_required
def disable_module(id, caseid):
    if id:
        if iris_module_disable_by_id(id):
            track_activity("IRIS module #{} disabled".format(id),
                           caseid=caseid, ctx_less=True)
            return response_success('')
        else:
            return response_error('Unable to disable module')

    return response_error('Malformed request', status=400)


@manage_modules_blueprint.route('/manage/modules/remove/<int:id>', methods=['GET', 'POST'])
@api_admin_required
def view_delete_module(id, caseid):
    try:

        delete_module_from_id(module_id=id)
        track_activity("IRIS module #{} deleted".format(id),
                       caseid=caseid, ctx_less=True)
        return response_success("Deleted")

    except Exception as e:
        log.error(e.__str__())
        return response_error("Cannot delete module. Error {}".format(e.__str__()))


@manage_modules_blueprint.route('/manage/modules/export-config/<int:id>', methods=['GET'])
@api_admin_required
def export_mod_config(id, caseid):

    mod_config, mod_name = get_module_config_from_id(id)
    if mod_name:
        data = {
            "module_name": mod_name,
            "module_configuration": mod_config
        }
        return response_success(data=data)

    return response_error(f"Module ID {id} not found")


@manage_modules_blueprint.route('/manage/modules/import-config/<int:id>', methods=['POST'])
@api_admin_required
def import_mod_config(id, caseid):

    mod_config, mod_name = get_module_config_from_id(id)

    for param in request.get_json():
        if iris_module_save_parameter(id, mod_config, param_name, parameter_value):
            track_activity("parameter {} of mod #{} was updated".format(param_name, mod_id),
                           caseid=caseid, ctx_less=True)
        return response_success("Saved")
    else:
        return response_error('Malformed request', status=400)


@manage_modules_blueprint.route('/manage/modules/hooks/list', methods=['GET'])
@api_admin_required
def view_modules_hook(caseid):
    output = module_list_hooks_view()
    data = [item._asdict() for item in output]

    return response_success('', data=data)
