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
import secrets

import marshmallow
from flask import Blueprint, request
from flask import render_template, url_for, redirect
from flask_login import current_user
from flask_wtf import FlaskForm

from app import db
from app.datamgmt.manage.manage_users_db import get_user, update_user
from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import UserSchema
from app.util import login_required, api_login_required, response_success, response_error

profile_blueprint = Blueprint('profile',
                              __name__,
                              template_folder='templates')


# CONTENT ------------------------------------------------
@profile_blueprint.route('/user/settings', methods=['GET'])
@login_required
def user_settings(caseid, url_redir):
    if url_redir:
        return redirect(url_for('profile.user_settings', cid=caseid))

    return render_template('profile.html')


@profile_blueprint.route('/user/token/renew', methods=['GET'])
@api_login_required
def user_renew_api(caseid):

    user = get_user(current_user.id)
    user.api_key = secrets.token_urlsafe(nbytes=64)

    db.session.commit()

    return response_success("Token renewed")


@profile_blueprint.route('/user/update/modal', methods=['GET'])
@login_required
def update_pwd_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('profile.user_settings', cid=caseid))

    form = FlaskForm()

    return render_template("modal_pwd_user.html", form=form)


@profile_blueprint.route('/user/update', methods=['POST'])
@api_login_required
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
                    user_isadmin=None,
                    user=user)
        db.session.commit()

        if cuser:
            track_activity("user {} updated itself".format(user.user), caseid=caseid)
            return response_success("User updated", data=user_schema.dump(user))

        return response_error("Unable to update user for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)