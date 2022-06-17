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
from werkzeug.utils import redirect

from app import db
from app.datamgmt.manage.manage_groups_db import delete_group
from app.datamgmt.manage.manage_groups_db import get_group
from app.datamgmt.manage.manage_groups_db import get_group_with_members
from app.datamgmt.manage.manage_groups_db import get_groups_list_hr_perms
from app.datamgmt.manage.manage_groups_db import remove_user_from_group
from app.datamgmt.manage.manage_groups_db import update_group_members
from app.datamgmt.manage.manage_organisations_db import delete_organisation
from app.datamgmt.manage.manage_organisations_db import get_org
from app.datamgmt.manage.manage_organisations_db import get_org_with_members
from app.datamgmt.manage.manage_organisations_db import get_organisations_list
from app.datamgmt.manage.manage_organisations_db import remove_user_from_organisation
from app.datamgmt.manage.manage_organisations_db import update_org_members
from app.datamgmt.manage.manage_users_db import get_user
from app.datamgmt.manage.manage_users_db import get_users_list
from app.forms import AddGroupForm
from app.forms import AddOrganisationForm
from app.iris_engine.access_control.utils import ac_get_all_permissions
from app.schema.marshables import AuthorizationGroupSchema
from app.schema.marshables import AuthorizationOrganisationSchema
from app.util import admin_required
from app.util import api_admin_required
from app.util import response_error
from app.util import response_success

manage_orgs_blueprint = Blueprint(
        'manage_orgs',
        __name__,
        template_folder='templates/access_control'
    )


@manage_orgs_blueprint.route('/manage/organisations/list', methods=['GET'])
@api_admin_required
def manage_orgs_index(caseid):
    groups = get_organisations_list()

    return response_success('', data=groups)


@manage_orgs_blueprint.route('/manage/organisations/<int:cur_id>/modal', methods=['GET'])
@admin_required
def manage_orgs_view_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_orgs.manage_orgs_index', cid=caseid))

    form = AddOrganisationForm()
    org = get_org_with_members(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    form.org_name.render_kw = {'value': org.org_name}
    form.org_description.render_kw = {'value': org.org_description}
    form.org_url.render_kw = {'value': org.org_url}
    form.org_email.render_kw = {'value': org.org_email}
    form.org_nationality.render_kw = {'value': org.org_nationality}
    form.org_sector.render_kw = {'value': org.org_sector}
    form.org_type.render_kw = {'org_type': org.org_type}

    return render_template("modal_add_org.html", form=form, org=org)


@manage_orgs_blueprint.route('/manage/organisations/<int:cur_id>', methods=['GET'])
@admin_required
def manage_orgs_view(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_orgs.manage_orgs_index', cid=caseid))

    org = get_org_with_members(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    return response_success("", data=org)


@manage_orgs_blueprint.route('/manage/organisations/add/modal', methods=['GET'])
@admin_required
def manage_orgs_add_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_orgs.manage_orgs_index', cid=caseid))

    form = AddOrganisationForm()

    return render_template("modal_add_org.html", form=form, org=None)


@manage_orgs_blueprint.route('/manage/organisations/add', methods=['POST'])
@api_admin_required
def manage_orgs_add(caseid):

    if not request.is_json:
        return response_error("Invalid request, expecting JSON")

    data = request.get_json()
    if not data:
        return response_error("Invalid request, expecting JSON")

    aos = AuthorizationOrganisationSchema()

    try:

        aos_c = aos.load(data)
        aos.verify_unique(data)

        db.session.add(aos_c)
        db.session.commit()

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)

    return response_success('', data=aos.dump(aos_c))


@manage_orgs_blueprint.route('/manage/organisations/update/<int:cur_id>', methods=['POST'])
@api_admin_required
def manage_org_update(cur_id, caseid):

    if not request.is_json:
        return response_error("Invalid request, expecting JSON")

    data = request.get_json()
    if not data:
        return response_error("Invalid request, expecting JSON")

    org = get_org(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    aos = AuthorizationOrganisationSchema()

    try:

        data['org_id'] = cur_id
        aos_c = aos.load(data, instance=org, partial=True)

        db.session.commit()

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)

    return response_success('', data=aos.dump(aos_c))


@manage_orgs_blueprint.route('/manage/organisations/delete/<int:cur_id>', methods=['GET'])
@api_admin_required
def manage_org_delete(cur_id, caseid):

    org = get_org(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    delete_organisation(org)

    return response_success('Organisation deleted')


@manage_orgs_blueprint.route('/manage/organisations/<int:cur_id>/members/modal', methods=['GET'])
@admin_required
def manage_org_members_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_orgs.manage_groups_index', cid=caseid))

    org = get_org_with_members(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    users = get_users_list()

    return render_template("modal_add_org_members.html", org=org, users=users)


@manage_orgs_blueprint.route('/manage/organisations/<int:cur_id>/members/update', methods=['POST'])
@api_admin_required
def manage_org_members_update(cur_id, caseid):

    org = get_org_with_members(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    if not request.is_json:
        return response_error("Invalid request, expecting JSON")

    data = request.get_json()
    if not data:
        return response_error("Invalid request, expecting JSON")

    if not isinstance(data.get('org_members'), list):
        return response_error("Expecting a list of IDs")

    update_org_members(org, data.get('org_members'))
    org = get_org_with_members(cur_id)

    return response_success('', data=org)


@manage_orgs_blueprint.route('/manage/organisations/<int:cur_id>/members/delete/<int:cur_id_2>', methods=['GET'])
@api_admin_required
def manage_groups_members_delete(cur_id, cur_id_2, caseid):

    org = get_org_with_members(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    user = get_user(cur_id_2)
    if not user:
        return response_error("Invalid user ID")

    remove_user_from_organisation(org, user)
    org = get_org_with_members(cur_id)

    return response_success('Member deleted from group', data=org)

