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

from app.blueprints.iris_user import iris_current_user
from app.datamgmt.client.client_db import get_client_list
from app.datamgmt.manage.manage_cases_db import list_cases_dict
from app.datamgmt.manage.manage_groups_db import get_groups_list
from app.datamgmt.manage.manage_srv_settings_db import get_srv_settings
from app.datamgmt.manage.manage_users_db import get_user_details
from app.datamgmt.manage.manage_users_db import get_user_effective_permissions
from app.forms import AddUserForm
from app.iris_engine.access_control.utils import ac_get_all_access_level
from app.models.authorization import Permissions
from app.blueprints.access_controls import ac_requires, ac_current_user_has_permission
from app.blueprints.responses import response_error

manage_users_blueprint = Blueprint('manage_users', __name__, template_folder='templates')


@manage_users_blueprint.route('/manage/users/add/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def add_user_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_users.add_user', cid=caseid))

    user = None
    form = AddUserForm()

    server_settings = get_srv_settings()

    return render_template("modal_add_user.html", form=form, user=user, server_settings=server_settings)


@manage_users_blueprint.route('/manage/users/<int:cur_id>/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def view_user_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_users.add_user', cid=caseid))

    form = AddUserForm()
    user = get_user_details(cur_id, include_api_key=True)

    if not user:
        return response_error("Invalid user ID")

    permissions = get_user_effective_permissions(cur_id)

    form.user_login.render_kw = {'value': user.get('user_login')}
    form.user_name.render_kw = {'value': user.get('user_name')}
    form.user_email.render_kw = {'value': user.get('user_email')}
    form.user_is_service_account.render_kw = {'checked': user.get('user_is_service_account')}

    server_settings = get_srv_settings()

    return render_template("modal_add_user.html", form=form, user=user, server_settings=server_settings,
                           permissions=permissions)


@manage_users_blueprint.route('/manage/users/<int:cur_id>/groups/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_user_group_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_users.add_user', cid=caseid))

    user = get_user_details(cur_id)
    if not user:
        return response_error("Invalid user ID")

    groups = get_groups_list()

    return render_template("modal_manage_user_groups.html", groups=groups, user=user)


@manage_users_blueprint.route('/manage/users/<int:cur_id>/customers/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_user_customers_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_users.add_user', cid=caseid))

    user = get_user_details(cur_id)
    if not user:
        return response_error("Invalid user ID")

    user_is_server_administrator = ac_current_user_has_permission(Permissions.server_administrator)
    groups = get_client_list(iris_current_user.id, user_is_server_administrator)

    return render_template("modal_manage_user_customers.html", groups=groups, user=user)


@manage_users_blueprint.route('/manage/users/<int:cur_id>/cases-access/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_user_cac_modal(cur_id, caseid, url_redir):

    if url_redir:
        return redirect(url_for('manage_users.add_user', cid=caseid))

    user = get_user_details(cur_id)
    if not user:
        return response_error("Invalid user ID")

    cases_list = list_cases_dict(iris_current_user.id)

    user_cases_access = [case.get('case_id') for case in user.get('user_cases_access')]
    outer_cases_list = []
    for case in cases_list:
        if case.get('case_id') not in user_cases_access:
            outer_cases_list.append({
                "case_id": case.get('case_id'),
                "case_name": case.get('case_name')
            })

    access_levels = ac_get_all_access_level()

    return render_template("modal_add_user_cac.html", user=user, outer_cases=outer_cases_list,
                           access_levels=access_levels)
