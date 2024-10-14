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

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import url_for
from flask_wtf import FlaskForm

from app.datamgmt.iris_engine.modules_db import parse_module_parameter
from app.datamgmt.iris_engine.modules_db import get_module_from_id
from app.datamgmt.iris_engine.modules_db import is_mod_configured
from app.forms import AddModuleForm
from app.forms import UpdateModuleParameterForm
from app.models.authorization import Permissions
from app.blueprints.access_controls import ac_requires
from app.blueprints.responses import response_error

manage_modules_blueprint = Blueprint(
    'manage_module',
    __name__,
    template_folder='templates'
)


@manage_modules_blueprint.route('/manage/modules', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_modules_index(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_module.manage_modules_index', cid=caseid))

    form = FlaskForm()

    return render_template("manage_modules.html", form=form)


@manage_modules_blueprint.route('/manage/modules/add/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def add_module_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_modules.add_module', cid=caseid))

    module = None
    form = AddModuleForm()

    return render_template("modal_add_module.html", form=form, module=module)


@manage_modules_blueprint.route('/manage/modules/get-parameter/<param_name>', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def getmodule_param(param_name, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_modules.add_module', cid=caseid))

    form = UpdateModuleParameterForm()

    mod_config, mod_id, mod_name, _, parameter = parse_module_parameter(param_name)

    if mod_config is None:
        return response_error('Invalid parameter')

    return render_template("modal_update_parameter.html", parameter=parameter, mod_name=mod_name, mod_id=mod_id,
                           form=form)


@manage_modules_blueprint.route('/manage/modules/update/<int:mod_id>/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def view_module(mod_id, caseid, url_redir):

    if url_redir:
        return redirect(url_for('manage_modules.view_module', cid=caseid, mod_id=mod_id))

    form = AddModuleForm()

    if mod_id:
        module = get_module_from_id(mod_id)
        config = module.module_config

        is_configured, missing_params = is_mod_configured(config)
        return render_template("modal_module_info.html", form=form, data=module,
                               config=config, is_configured=is_configured, missing_params=missing_params)

    return response_error('Malformed request')
