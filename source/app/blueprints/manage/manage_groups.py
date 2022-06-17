#!/usr/bin/env python3
#
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
import marshmallow
from flask import Blueprint
from flask import render_template
from flask import request
from flask import url_for
from flask_wtf import FlaskForm
from werkzeug.utils import redirect

from app import db
from app.datamgmt.manage.manage_groups_db import get_group
from app.datamgmt.manage.manage_groups_db import get_group_with_members
from app.datamgmt.manage.manage_groups_db import get_groups_list
from app.datamgmt.manage.manage_groups_db import get_groups_list_hr_perms
from app.datamgmt.manage.manage_groups_db import remove_user_from_group
from app.datamgmt.manage.manage_groups_db import update_group_members
from app.datamgmt.manage.manage_users_db import get_user
from app.datamgmt.manage.manage_users_db import get_users_list
from app.forms import AddGroupForm
from app.iris_engine.access_control.utils import ac_get_all_permissions
from app.models.authorization import Group
from app.schema.marshables import AuthorizationGroupSchema
from app.util import admin_required
from app.util import api_admin_required
from app.util import response_error
from app.util import response_success

manage_groups_blueprint = Blueprint(
        'manage_groups',
        __name__,
        template_folder='templates'
    )


@manage_groups_blueprint.route('/manage/groups/list', methods=['GET'])
@api_admin_required
def manage_groups_index(caseid):
    groups = get_groups_list_hr_perms()

    return response_success('', data=groups)


@manage_groups_blueprint.route('/manage/groups/<int:cur_id>/modal', methods=['GET'])
@admin_required
def manage_groups_view_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_groups_blueprint.manage_groups_index', cid=caseid))

    form = AddGroupForm()
    group = get_group_with_members(cur_id)
    if not group:
        return response_error("Invalid group ID")

    all_perms = ac_get_all_permissions()

    form.group_name.render_kw = {'value': group.group_name}
    form.group_description.render_kw = {'value': group.group_description}

    return render_template("modal_add_group.html", form=form, group=group, all_perms=all_perms)


@manage_groups_blueprint.route('/manage/groups/add/modal', methods=['GET'])
@admin_required
def manage_groups_add_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_groups_blueprint.manage_groups_index', cid=caseid))

    form = AddGroupForm()

    all_perms = ac_get_all_permissions()

    return render_template("modal_add_group.html", form=form, group=None, all_perms=all_perms)


@manage_groups_blueprint.route('/manage/groups/add', methods=['POST'])
@api_admin_required
def manage_groups_add(caseid):

    if not request.is_json:
        return response_error("Invalid request, expecting JSON")

    data = request.get_json()
    if not data:
        return response_error("Invalid request, expecting JSON")

    ags = AuthorizationGroupSchema()

    try:

        ags_c = ags.load(data)
        db.session.add(ags_c)
        db.session.commit()

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)

    return response_success('', data=ags.dump(ags_c))


@manage_groups_blueprint.route('/manage/groups/<int:cur_id>', methods=['GET'])
@api_admin_required
def manage_groups_view(cur_id, caseid):

    group = get_group_with_members(cur_id)
    if not group:
        return response_error("Invalid group ID")

    return response_success('', data=group)


@manage_groups_blueprint.route('/manage/groups/<int:cur_id>/members/modal', methods=['GET'])
@admin_required
def manage_groups_members_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_groups_blueprint.manage_groups_index', cid=caseid))

    group = get_group_with_members(cur_id)
    if not group:
        return response_error("Invalid group ID")

    users = get_users_list()

    return render_template("modal_add_group_members.html", group=group, users=users)


@manage_groups_blueprint.route('/manage/groups/<int:cur_id>/members/update', methods=['POST'])
@api_admin_required
def manage_groups_members_update(cur_id, caseid):

    group = get_group_with_members(cur_id)
    if not group:
        return response_error("Invalid group ID")

    if not request.is_json:
        return response_error("Invalid request, expecting JSON")

    data = request.get_json()
    if not data:
        return response_error("Invalid request, expecting JSON")

    if not isinstance(data.get('group_members'), list):
        return response_error("Expecting a list of IDs")

    update_group_members(group, data.get('group_members'))

    return response_success('', data=group)


@manage_groups_blueprint.route('/manage/groups/<int:cur_id>/members/delete/<int:cur_id_2>', methods=['GET'])
@api_admin_required
def manage_groups_members_delete(cur_id, cur_id_2, caseid):

    group = get_group_with_members(cur_id)
    if not group:
        return response_error("Invalid group ID")

    user = get_user(cur_id_2)
    if not user:
        return response_error("Invalid user ID")

    group = remove_user_from_group(group, user)

    return response_success('Member deleted from group', data=group)

