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
import traceback

import marshmallow
from flask import Blueprint
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from werkzeug.utils import redirect

from app import db
from app import app
from app.datamgmt.manage.manage_cases_db import list_cases_dict
from app.datamgmt.manage.manage_groups_db import add_all_cases_access_to_group
from app.datamgmt.manage.manage_groups_db import add_case_access_to_group
from app.datamgmt.manage.manage_groups_db import delete_group
from app.datamgmt.manage.manage_groups_db import get_group
from app.datamgmt.manage.manage_groups_db import get_group_details
from app.datamgmt.manage.manage_groups_db import get_group_with_members
from app.datamgmt.manage.manage_groups_db import get_groups_list_hr_perms
from app.datamgmt.manage.manage_groups_db import remove_cases_access_from_group
from app.datamgmt.manage.manage_groups_db import remove_user_from_group
from app.datamgmt.manage.manage_groups_db import update_group_members
from app.datamgmt.manage.manage_users_db import get_user
from app.datamgmt.manage.manage_users_db import get_users_list_restricted
from app.forms import AddGroupForm
from app.iris_engine.access_control.utils import ac_get_all_access_level
from app.iris_engine.access_control.utils import ac_ldp_group_removal
from app.iris_engine.access_control.utils import ac_flag_match_mask
from app.iris_engine.access_control.utils import ac_ldp_group_update
from app.iris_engine.access_control.utils import ac_get_all_permissions
from app.iris_engine.access_control.utils import ac_recompute_effective_ac_from_users_list
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.schema.marshables import AuthorizationGroupSchema
from app.util import ac_api_requires
from app.util import ac_api_return_access_denied
from app.util import ac_requires
from app.util import response_error
from app.util import response_success
from app.iris_engine.demo_builder import protect_demo_mode_group

manage_groups_blueprint = Blueprint(
        'manage_groups',
        __name__,
        template_folder='templates/access_control'
    )


log = app.logger


@manage_groups_blueprint.route('/manage/groups/list', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def manage_groups_index():
    groups = get_groups_list_hr_perms()

    return response_success('', data=groups)


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


@manage_groups_blueprint.route('/manage/groups/add', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def manage_groups_add():

    if not request.is_json:
        return response_error("Invalid request, expecting JSON")

    data = request.get_json()
    if not data:
        return response_error("Invalid request, expecting JSON")

    ags = AuthorizationGroupSchema()

    try:

        ags_c = ags.load(data)
        ags.verify_unique(data)

        db.session.add(ags_c)
        db.session.commit()

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    track_activity(message=f"added group {ags_c.group_name}", ctx_less=True)

    return response_success('', data=ags.dump(ags_c))


@manage_groups_blueprint.route('/manage/groups/update/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def manage_groups_update(cur_id):

    if not request.is_json:
        return response_error("Invalid request, expecting JSON")

    data = request.get_json()
    if not data:
        return response_error("Invalid request, expecting JSON")

    group = get_group(cur_id)
    if not group:
        return response_error("Invalid group ID")

    if protect_demo_mode_group(group):
        return ac_api_return_access_denied()

    ags = AuthorizationGroupSchema()

    try:

        data['group_id'] = cur_id
        ags_c = ags.load(data, instance=group, partial=True)

        if not ac_flag_match_mask(data['group_permissions'],
                                  Permissions.server_administrator.value):

            if ac_ldp_group_update(current_user.id):
                db.session.rollback()
                return response_error(msg="That might not be a good idea Dave",
                                      data="Update the group permissions will lock you out")

        db.session.commit()

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    return response_success('', data=ags.dump(ags_c))


@manage_groups_blueprint.route('/manage/groups/delete/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def manage_groups_delete(cur_id):

    group = get_group(cur_id)
    if not group:
        return response_error("Invalid group ID")

    if protect_demo_mode_group(group):
        return ac_api_return_access_denied()

    if ac_ldp_group_removal(current_user.id, group_id=group.group_id):
        return response_error("I can't let you do that Dave", data="Removing this group will lock you out")

    delete_group(group)

    return response_success('Group deleted')


@manage_groups_blueprint.route('/manage/groups/<int:cur_id>', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def manage_groups_view(cur_id):

    group = get_group_details(cur_id)
    if not group:
        return response_error("Invalid group ID")

    ags = AuthorizationGroupSchema()
    return response_success('', data=ags.dump(group))


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


@manage_groups_blueprint.route('/manage/groups/<int:cur_id>/members/update', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def manage_groups_members_update(cur_id):

    group = get_group_with_members(cur_id)
    if not group:
        return response_error("Invalid group ID")

    if protect_demo_mode_group(group):
        return ac_api_return_access_denied()

    if not request.is_json:
        return response_error("Invalid request, expecting JSON")

    data = request.get_json()
    if not data:
        return response_error("Invalid request, expecting JSON")

    if not isinstance(data.get('group_members'), list):
        return response_error("Expecting a list of IDs")

    update_group_members(group, data.get('group_members'))
    group = get_group_with_members(cur_id)

    return response_success('', data=group)


@manage_groups_blueprint.route('/manage/groups/<int:cur_id>/members/delete/<int:cur_id_2>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def manage_groups_members_delete(cur_id, cur_id_2):

    group = get_group_with_members(cur_id)
    if not group:
        return response_error("Invalid group ID")

    if protect_demo_mode_group(group):
        return ac_api_return_access_denied()

    user = get_user(cur_id_2)
    if not user:
        return response_error("Invalid user ID")

    if ac_ldp_group_removal(user_id=user.id, group_id=group.group_id):
        return response_error('I cannot let you do that Dave', data="Removing you from the group will make you "
                                                                    "loose your access rights")

    remove_user_from_group(group, user)
    group = get_group_with_members(cur_id)

    return response_success('Member deleted from group', data=group)


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


@manage_groups_blueprint.route('/manage/groups/<int:cur_id>/cases-access/update', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def manage_groups_cac_add_case(cur_id):
    if not request.is_json:
        return response_error("Invalid request, expecting JSON")

    data = request.get_json()
    if not data:
        return response_error("Invalid request, expecting JSON")

    group = get_group_with_members(cur_id)
    if not group:
        return response_error("Invalid group ID")

    if protect_demo_mode_group(group):
        return ac_api_return_access_denied()

    if not isinstance(data.get('access_level'), int):
        try:
            data['access_level'] = int(data.get('access_level'))
        except:
            return response_error("Expecting access_level as int")

    if not isinstance(data.get('cases_list'), list) and data.get('auto_follow_cases') is False:
        return response_error("Expecting cases_list as list")

    if data.get('auto_follow_cases') is True:
        group, logs = add_all_cases_access_to_group(group, data.get('access_level'))
        group.group_auto_follow = True
        group.group_auto_follow_access_level = data.get('access_level')
        db.session.commit()
    else:
        group, logs = add_case_access_to_group(group, data.get('cases_list'), data.get('access_level'))
        group.group_auto_follow = False
        db.session.commit()

    if not group:
        return response_error(msg=logs)

    group = get_group_details(cur_id)

    ac_recompute_effective_ac_from_users_list(group.group_members)

    return response_success(data=group)


@manage_groups_blueprint.route('/manage/groups/<int:cur_id>/cases-access/delete', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def manage_groups_cac_delete_case(cur_id):

    group = get_group_with_members(cur_id)
    if not group:
        return response_error("Invalid group ID")

    if protect_demo_mode_group(group):
        return ac_api_return_access_denied()

    if not request.is_json:
        return response_error("Invalid request")

    data = request.get_json()
    if not data:
        return response_error("Invalid request")

    if not isinstance(data.get('cases'), list):
        return response_error("Expecting cases as list")

    try:

        success, logs = remove_cases_access_from_group(group.group_id, data.get('cases'))
        db.session.commit()

    except Exception as e:
        log.error("Error while removing cases access from group: {}".format(e))
        log.error(traceback.format_exc())
        return response_error(msg=str(e))

    if success:
        ac_recompute_effective_ac_from_users_list(group.group_members)
        return response_success(msg="Cases access removed from group")

    return response_error(msg=logs)
