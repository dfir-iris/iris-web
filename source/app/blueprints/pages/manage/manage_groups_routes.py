#  IRIS Source Code
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
from flask import render_template
from flask import url_for
from flask_login import current_user
from werkzeug.utils import redirect

from app.datamgmt.manage.manage_cases_db import list_cases_dict
from app.datamgmt.manage.manage_groups_db import get_group_details
from app.datamgmt.manage.manage_groups_db import get_group_with_members
from app.datamgmt.manage.manage_users_db import get_users_list_restricted
from app.forms import AddGroupForm
from app.iris_engine.access_control.utils import ac_get_all_access_level
from app.iris_engine.access_control.utils import ac_get_all_permissions
from app.models.authorization import Permissions
from app.blueprints.access_controls import ac_requires
from app.blueprints.responses import response_error

manage_groups_blueprint = Blueprint(
        'manage_groups',
        __name__,
        template_folder='templates/access_control'
    )


@manage_groups_blueprint.route('/manage/groups/<int:cur_id>/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_groups_view_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_groups.manage_groups_index', cid=caseid))

    form = AddGroupForm()
    group = get_group_details(cur_id)
    if not group:
        return response_error("Invalid group ID")

    all_perms = ac_get_all_permissions()

    form.group_name.render_kw = {'value': group.group_name}
    form.group_description.render_kw = {'value': group.group_description}

    return render_template("modal_add_group.html", form=form, group=group, all_perms=all_perms)


@manage_groups_blueprint.route('/manage/groups/add/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_groups_add_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_groups.manage_groups_index', cid=caseid))

    form = AddGroupForm()

    all_perms = ac_get_all_permissions()

    return render_template("modal_add_group.html", form=form, group=None, all_perms=all_perms)


@manage_groups_blueprint.route('/manage/groups/<int:cur_id>/members/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_groups_members_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_groups_blueprint.manage_groups_index', cid=caseid))

    group = get_group_with_members(cur_id)
    if not group:
        return response_error("Invalid group ID")

    users = get_users_list_restricted()

    return render_template("modal_add_group_members.html", group=group, users=users)


@manage_groups_blueprint.route('/manage/groups/<int:cur_id>/cases-access/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_groups_cac_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_groups.manage_groups_index', cid=caseid))

    group = get_group_details(cur_id)
    if not group:
        return response_error("Invalid group ID")

    cases_list = list_cases_dict(current_user.id)
    group_cases_access = [case.get('case_id') for case in group.group_cases_access]
    outer_cases_list = []
    for case in cases_list:
        if case.get('case_id') not in group_cases_access:
            outer_cases_list.append({
                "case_id": case.get('case_id'),
                "case_name": case.get('case_name')
            })

    access_levels = ac_get_all_access_level()

    return render_template("modal_add_group_cac.html", group=group, outer_cases=outer_cases_list,
                           access_levels=access_levels)
