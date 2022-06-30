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
from flask import session
from flask import url_for
from flask_login import current_user
from werkzeug.utils import redirect

from app import db
from app.datamgmt.case.case_db import get_case
from app.datamgmt.manage.manage_cases_db import list_cases_dict
from app.datamgmt.manage.manage_organisations_db import add_case_access_to_org
from app.datamgmt.manage.manage_organisations_db import delete_organisation
from app.datamgmt.manage.manage_organisations_db import get_org
from app.datamgmt.manage.manage_organisations_db import get_org_with_members
from app.datamgmt.manage.manage_organisations_db import get_organisations_list
from app.datamgmt.manage.manage_organisations_db import get_orgs_details
from app.datamgmt.manage.manage_organisations_db import get_user_organisations
from app.datamgmt.manage.manage_organisations_db import is_user_in_org
from app.datamgmt.manage.manage_organisations_db import remove_case_access_from_organisation
from app.datamgmt.manage.manage_organisations_db import remove_user_from_organisation
from app.datamgmt.manage.manage_organisations_db import update_org_members
from app.datamgmt.manage.manage_users_db import get_user
from app.datamgmt.manage.manage_users_db import get_users_list
from app.forms import AddOrganisationForm
from app.iris_engine.access_control.utils import ac_get_all_access_level
from app.models.authorization import Permissions
from app.schema.marshables import AuthorizationOrganisationSchema
from app.util import ac_api_requires
from app.util import ac_requires
from app.util import response_error
from app.util import response_success

manage_orgs_blueprint = Blueprint(
        'manage_orgs',
        __name__,
        template_folder='templates/access_control'
    )


@manage_orgs_blueprint.route('/manage/organisations/list', methods=['GET'])
@ac_api_requires(Permissions.manage_own_organisation, Permissions.manage_organisations)
def manage_orgs_index(caseid):

    if not session['permissions'] & Permissions.manage_organisations.value:
        organisations = get_user_organisations(current_user.id)
    else:
        organisations = get_organisations_list()

    return response_success('', data=organisations)


@manage_orgs_blueprint.route('/manage/organisations/<int:cur_id>/modal', methods=['GET'])
@ac_requires(Permissions.manage_own_organisation, Permissions.manage_organisations)
def manage_orgs_view_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_orgs.manage_orgs_index', cid=caseid))

    if not session['permissions'] & Permissions.manage_organisations.value:
        if not is_user_in_org(current_user.id, cur_id):
            return response_error('Access denied', status=403)

    form = AddOrganisationForm()
    org = get_orgs_details(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    form.org_name.render_kw = {'value': org.org_name}
    form.org_description.render_kw = {'value': org.org_description}
    form.org_url.render_kw = {'value': org.org_url}
    form.org_email.render_kw = {'value': org.org_email}
    form.org_nationality.render_kw = {'value': org.org_nationality}
    form.org_sector.render_kw = {'value': org.org_sector}
    form.org_type.render_kw = {'value': org.org_type}

    return render_template("modal_add_org.html", form=form, org=org)


@manage_orgs_blueprint.route('/manage/organisations/<int:cur_id>', methods=['GET'])
@ac_api_requires(Permissions.manage_own_organisation, Permissions.manage_organisations)
def manage_orgs_view(cur_id, caseid):

    if not session['permissions'] & Permissions.manage_organisations.value:
        if not is_user_in_org(current_user.id, cur_id):
            return response_error('Access denied', status=403)

    org = get_orgs_details(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    return response_success("", data=org)


@manage_orgs_blueprint.route('/manage/organisations/add/modal', methods=['GET'])
@ac_requires(Permissions.manage_organisations)
def manage_orgs_add_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_orgs.manage_orgs_index', cid=caseid))

    form = AddOrganisationForm()

    return render_template("modal_add_org.html", form=form, org=None)


@manage_orgs_blueprint.route('/manage/organisations/add', methods=['POST'])
@ac_api_requires(Permissions.manage_organisations)
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
@ac_api_requires(Permissions.manage_own_organisation, Permissions.manage_organisations)
def manage_org_update(cur_id, caseid):

    if not request.is_json:
        return response_error("Invalid request, expecting JSON")

    data = request.get_json()
    if not data:
        return response_error("Invalid request, expecting JSON")

    if not session['permissions'] & Permissions.manage_organisations.value:
        if not is_user_in_org(current_user.id, cur_id):
            return response_error('Access denied', status=403)

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
@ac_api_requires(Permissions.manage_organisations)
def manage_org_delete(cur_id, caseid):

    org = get_org(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    delete_organisation(org)

    return response_success('Organisation deleted')


@manage_orgs_blueprint.route('/manage/organisations/<int:cur_id>/members/modal', methods=['GET'])
@ac_requires(Permissions.manage_own_organisation, Permissions.manage_organisations)
def manage_org_members_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_orgs.manage_groups_index', cid=caseid))

    if not session['permissions'] & Permissions.manage_organisations.value:
        if not is_user_in_org(current_user.id, cur_id):
            return response_error('Access denied', status=403)

    org = get_org_with_members(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    users = get_users_list()

    return render_template("modal_add_org_members.html", org=org, users=users)


@manage_orgs_blueprint.route('/manage/organisations/<int:cur_id>/members/update', methods=['POST'])
@ac_api_requires(Permissions.manage_own_organisation, Permissions.manage_organisations)
def manage_org_members_update(cur_id, caseid):
    if not request.is_json:
        return response_error("Invalid request, expecting JSON")

    data = request.get_json()
    if not data:
        return response_error("Invalid request, expecting JSON")

    if not session['permissions'] & Permissions.manage_organisations.value:
        if not is_user_in_org(current_user.id, cur_id):
            return response_error('Access denied', status=403)

    org = get_org_with_members(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    if not isinstance(data.get('org_members'), list):
        return response_error("Expecting a list of IDs")

    update_org_members(org, data.get('org_members'))
    org = get_org_with_members(cur_id)

    return response_success('', data=org)


@manage_orgs_blueprint.route('/manage/organisations/<int:cur_id>/members/delete/<int:cur_id_2>', methods=['GET'])
@ac_api_requires(Permissions.manage_own_organisation, Permissions.manage_organisations)
def manage_groups_members_delete(cur_id, cur_id_2, caseid):

    if not session['permissions'] & Permissions.manage_organisations.value:
        if not is_user_in_org(current_user.id, cur_id):
            return response_error('Access denied', status=403)

    org = get_org_with_members(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    user = get_user(cur_id_2)
    if not user:
        return response_error("Invalid user ID")

    remove_user_from_organisation(org, user)
    org = get_org_with_members(cur_id)

    return response_success('Member deleted from group', data=org)


@manage_orgs_blueprint.route('/manage/organisations/<int:cur_id>/cases-access/modal', methods=['GET'])
@ac_requires(Permissions.manage_own_organisation, Permissions.manage_organisations)
def manage_org_cac_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_orgs.manage_orgs_index', cid=caseid))

    if not session['permissions'] & Permissions.manage_organisations.value:
        if not is_user_in_org(current_user.id, cur_id):
            return response_error('Access denied', status=403)

    org = get_orgs_details(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    cases_list = list_cases_dict(current_user.id)
    org_cases_access = [case.get('case_id') for case in org.org_cases_access]
    outer_cases_list = []
    for case in cases_list:
        if case.get('case_id') not in org_cases_access:
            outer_cases_list.append({
                "case_id": case.get('case_id'),
                "case_name": case.get('case_name')
            })

    access_levels = ac_get_all_access_level()

    return render_template("modal_add_org_cac.html", org=org, outer_cases=outer_cases_list, access_levels=access_levels)


@manage_orgs_blueprint.route('/manage/organisations/<int:cur_id>/cases-access/add', methods=['POST'])
@ac_api_requires(Permissions.manage_own_organisation, Permissions.manage_organisations)
def manage_org_cac_add_case(cur_id, caseid):
    if not request.is_json:
        return response_error("Invalid request, expecting JSON")

    data = request.get_json()
    if not data:
        return response_error("Invalid request, expecting JSON")

    if not session['permissions'] & Permissions.manage_organisations.value:
        if not is_user_in_org(current_user.id, cur_id):
            return response_error('Access denied', status=403)

    org = get_org(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    if not isinstance(data.get('case_id'), int):
        try:
            data['case_id'] = int(data.get('case_id'))
        except:
            return response_error("Expecting case_id as int")

    if not isinstance(data.get('access_level'), list):
        return response_error("Expecting access_level as list")

    org, logs = add_case_access_to_org(org, data.get('case_id'), data.get('access_level'))
    if not org:
        return response_error(msg=logs)

    org = get_orgs_details(cur_id)

    return response_success(data=org)


@manage_orgs_blueprint.route('/manage/organisations/<int:cur_id>/cases-access/delete/<int:cur_id_2>', methods=['GET'])
@ac_api_requires(Permissions.manage_own_organisation, Permissions.manage_organisations)
def manage_groups_ac_delete_case(cur_id, cur_id_2, caseid):

    if not session['permissions'] & Permissions.manage_organisations.value:
        if not is_user_in_org(current_user.id, cur_id):
            return response_error('Access denied', status=403)

    org = get_org(cur_id)
    if not org:
        return response_error("Invalid organisation ID")

    case = get_case(cur_id_2)
    if not case:
        return response_error("Invalid case ID")

    remove_case_access_from_organisation(org.org_id, case.case_id)
    org = get_orgs_details(cur_id)

    return response_success('Case access removed from organisation', data=org)
