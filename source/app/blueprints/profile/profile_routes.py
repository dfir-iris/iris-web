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

import marshmallow
# IMPORTS ------------------------------------------------
import secrets
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask_login import current_user
from flask_wtf import FlaskForm

from app import db
from app.datamgmt.manage.manage_srv_settings_db import get_srv_settings
from app.datamgmt.manage.manage_users_db import get_user
from app.datamgmt.manage.manage_users_db import update_user
from app.iris_engine.access_control.utils import ac_get_effective_permissions_of_user
from app.iris_engine.access_control.utils import ac_recompute_effective_ac
from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import UserSchema
from app.util import ac_api_requires
from app.util import ac_requires
from app.util import response_error
from app.util import response_success

profile_blueprint = Blueprint('profile',
                              __name__,
                              template_folder='templates')


# CONTENT ------------------------------------------------
@profile_blueprint.route('/user/settings', methods=['GET'])
@ac_requires()
def user_settings(caseid, url_redir):
    if url_redir:
        return redirect(url_for('profile.user_settings', cid=caseid))

    return render_template('profile.html')


@profile_blueprint.route('/user/token/renew', methods=['GET'])
@ac_api_requires()
def user_renew_api(caseid):

    user = get_user(current_user.id)
    user.api_key = secrets.token_urlsafe(nbytes=64)

    db.session.commit()

    return response_success("Token renewed")


@profile_blueprint.route('/user/is-admin', methods=['GET'])
@ac_api_requires()
def user_is_admin(caseid):

    roles = [role.name for role in current_user.roles]
    if "administrator" not in roles:
        return response_error('User is not administrator', status=401)

    return response_success("User is administrator")


@profile_blueprint.route('/user/update/modal', methods=['GET'])
@ac_requires()
def update_pwd_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('profile.user_settings', cid=caseid))

    form = FlaskForm()

    server_settings = get_srv_settings()

    return render_template("modal_pwd_user.html", form=form, server_settings=server_settings)


@profile_blueprint.route('/user/update', methods=['POST'])
@ac_api_requires()
def update_user_view(caseid):
    try:
        user = get_user(current_user.id)
        if not user:
            return response_error("Invalid user ID for this case")

        # validate before saving
        user_schema = UserSchema()
        jsdata = request.get_json()
        jsdata['user_id'] = current_user.id
        cuser = user_schema.load(jsdata, instance=user, partial=True)
        update_user(password=jsdata.get('user_password'),
                    user=user)
        db.session.commit()

        if cuser:
            track_activity("user {} updated itself".format(user.user), caseid=caseid)
            return response_success("User updated", data=user_schema.dump(user))

        return response_error("Unable to update user for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@profile_blueprint.route('/user/theme/set/<theme>', methods=['GET'])
@ac_api_requires()
def profile_set_theme(theme, caseid):
    if theme not in ['dark', 'light']:
        return response_error('Invalid data')

    user = get_user(current_user.id)
    if not user:
        return response_error("Invalid user ID")

    user.in_dark_mode = (theme == 'dark')
    db.session.commit()

    return response_success('Theme changed')


@profile_blueprint.route('/user/refresh-permissions', methods=['GET'])
@ac_api_requires()
def profile_refresh_permissions_and_ac(caseid):

    user = get_user(current_user.id)
    if not user:
        return response_error("Invalid user ID")

    ac_recompute_effective_ac(current_user.id)
    session['permissions'] = ac_get_effective_permissions_of_user(user)

    return response_success('Access control and permissions refreshed')

