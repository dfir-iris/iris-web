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

import marshmallow
import secrets
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask_login import current_user
from flask_wtf import FlaskForm

from app import db, app
from app.datamgmt.manage.manage_srv_settings_db import get_srv_settings, get_server_settings_as_dict
from app.datamgmt.manage.manage_users_db import get_user
from app.datamgmt.manage.manage_users_db import get_user_primary_org
from app.datamgmt.manage.manage_users_db import update_user
from app.iris_engine.access_control.utils import ac_current_user_has_permission
from app.iris_engine.access_control.utils import ac_get_effective_permissions_of_user
from app.iris_engine.access_control.utils import ac_recompute_effective_ac
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.schema.marshables import UserSchema
from app.schema.marshables import BasicUserSchema
from app.util import ac_api_requires
from app.util import ac_requires
from app.util import endpoint_deprecated
from app.util import response_error
from app.util import response_success

profile_blueprint = Blueprint('profile',
                              __name__,
                              template_folder='templates')


# CONTENT ------------------------------------------------
@profile_blueprint.route('/user/settings', methods=['GET'])
@ac_requires(no_cid_required=True)
def user_settings(caseid, url_redir):
    if url_redir:
        return redirect(url_for('profile.user_settings', cid=caseid))

    if 'SERVER_SETTINGS' not in app.config:
        app.config['SERVER_SETTINGS'] = get_server_settings_as_dict()

    return render_template('profile.html', mfa_enabled=app.config['SERVER_SETTINGS']['enforce_mfa'])


@profile_blueprint.route('/user/token/renew', methods=['GET'])
@ac_api_requires()
def user_renew_api():

    user = get_user(current_user.id)
    user.api_key = secrets.token_urlsafe(nbytes=64)

    db.session.commit()

    return response_success("Token renewed")


@profile_blueprint.route('/user/is-admin', methods=['GET'])
@endpoint_deprecated('Use /user/has-permission to check permission', 'v1.5.0')
def user_is_admin(caseid):
    pass


@profile_blueprint.route('/user/has-permission', methods=['POST'])
@ac_api_requires()
def user_has_permission():

    req_js = request.json
    if not req_js:
        return response_error('Invalid request')

    if not req_js.get('permission_name') or not \
            req_js.get('permission_value'):
        return response_error('Invalid request')

    if req_js.get('permission_value') not in Permissions._value2member_map_:
        return response_error('Invalid permission')

    if Permissions(req_js.get('permission_value')).name.lower() != req_js.get('permission_name').lower():
        return response_error('Permission value-name mismatch')

    if ac_current_user_has_permission(Permissions(req_js.get('permission_value'))):
        return response_success('User has permission')
    else:
        return response_error('User does not have permission', status=403)


@profile_blueprint.route('/user/update/modal', methods=['GET'])
@ac_requires(no_cid_required=True)
def update_pwd_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('profile.user_settings', cid=caseid))

    form = FlaskForm()

    server_settings = get_srv_settings()

    return render_template("modal_pwd_user.html", form=form, server_settings=server_settings)


@profile_blueprint.route('/user/update', methods=['POST'])
@ac_api_requires()
def update_user_view():
    try:
        user = get_user(current_user.id)
        if not user:
            return response_error("Invalid user ID for this case")

        # validate before saving
        user_schema = UserSchema()
        jsdata = request.get_json()
        jsdata['user_id'] = current_user.id
        puo = get_user_primary_org(current_user.id)

        jsdata['user_primary_organisation_id'] = puo.org_id

        cuser = user_schema.load(jsdata, instance=user, partial=True)
        update_user(password=jsdata.get('user_password'),
                    user=user)
        db.session.commit()

        if cuser:
            track_activity("user {} updated itself".format(user.user))
            return response_success("User updated", data=user_schema.dump(user))

        return response_error("Unable to update user for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@profile_blueprint.route('/user/theme/set/<string:theme>', methods=['GET'])
@ac_api_requires()
def profile_set_theme(theme):
    if theme not in ['dark', 'light']:
        return response_error('Invalid data')

    user = get_user(current_user.id)
    if not user:
        return response_error("Invalid user ID")

    user.in_dark_mode = (theme == 'dark')
    db.session.commit()

    return response_success('Theme changed')


@profile_blueprint.route('/user/deletion-prompt/set/<string:val>', methods=['GET'])
@ac_api_requires()
def profile_set_deletion_prompt(val):
    if val not in ['true', 'false']:
        return response_error('Invalid data')

    user = get_user(current_user.id)
    if not user:
        return response_error("Invalid user ID")

    user.has_deletion_confirmation = (val == 'true')
    db.session.commit()

    return response_success('Deletion prompt {}'.format('enabled' if val == 'true' else 'disabled'))


@profile_blueprint.route('/user/mini-sidebar/set/<string:val>', methods=['GET'])
@ac_api_requires()
def profile_set_minisidebar(val):
    if val not in ['true', 'false']:
        return response_error('Invalid data')

    user = get_user(current_user.id)
    if not user:
        return response_error("Invalid user ID")

    user.has_mini_sidebar = (val == 'true')
    db.session.commit()

    return response_success('Mini sidebar {}'.format('enabled' if val == 'true' else 'disabled'))


@profile_blueprint.route('/user/refresh-permissions', methods=['GET'])
@ac_api_requires()
def profile_refresh_permissions_and_ac():

    user = get_user(current_user.id)
    if not user:
        return response_error("Invalid user ID")

    ac_recompute_effective_ac(current_user.id)
    session['permissions'] = ac_get_effective_permissions_of_user(user)

    return response_success('Access control and permissions refreshed')


@profile_blueprint.route('/user/whoami', methods=['GET'])
@ac_api_requires()
def profile_whoami():
    """
    Returns the current user's profile
    """
    user = get_user(current_user.id)
    if not user:
        return response_error("Invalid user ID")

    user_schema = BasicUserSchema()
    return response_success(data=user_schema.dump(user))
