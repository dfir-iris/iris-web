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

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask_login import current_user
from flask_login import login_user

from app import app
from app import bc
from app import db

from app.forms import LoginForm
from app.iris_engine.access_control.ldap_handler import ldap_authenticate
from app.iris_engine.access_control.utils import ac_get_effective_permissions_of_user
from app.iris_engine.utils.tracker import track_activity
from app.models.cases import Cases
from app.models.authorization import User
from app.util import is_authentication_ldap


login_blueprint = Blueprint(
    'login',
    __name__,
    template_folder='templates'
)

log = app.logger


# CONTENT ------------------------------------------------
# Authenticate user
if app.config.get("AUTHENTICATION_TYPE") in ["local", "ldap"]:
    @login_blueprint.route('/login', methods=['GET', 'POST'])
    def login():
        session.permanent = True

        if current_user.is_authenticated:
            return redirect(url_for('index.index'))

        form = LoginForm(request.form)
        msg = None

        if form.validate_on_submit():
            username = form.username.data
            password = form.password.data

            user = User.query.filter(
                User.user == username,
                User.active.is_(True),
                User.is_service_account.is_(False)
            ).first()

            if user:
                if is_authentication_ldap() is True:
                    try:
                        if ldap_authenticate(username, password) is True:
                            return wrap_login_user(user)

                        else:
                            track_activity("wrong login password for user '{}' using LDAP auth".format(username),
                                           ctx_less=True, display_in_ui=False)

                            msg = "Wrong credentials. Please try again."
                            return render_template('login.html', form=form, msg=msg)

                    except Exception as e:
                        log.error(e.__str__())
                        return render_template('login.html', form=form,
                                               msg='LDAP authentication unavailable. Check server logs')

                elif bc.check_password_hash(user.password, password):
                    return wrap_login_user(user)

                else:
                    track_activity("wrong login password for user '{}' using local auth".format(username),
                                   ctx_less=True,
                                   display_in_ui=False)
                    msg = "Wrong credentials. Please try again."

            else:
                track_activity("someone tried to log in with user '{}', which does not exist".format(username),
                               ctx_less=True, display_in_ui=False)
                msg = "Wrong credentials. Please try again."

        return render_template('login.html', form=form, msg=msg,
                               organisation_name=app.config.get('ORGANISATION_NAME'))


def wrap_login_user(user):
    login_user(user)

    track_activity("user '{}' successfully logged-in".format(user.user), ctx_less=True, display_in_ui=False)
    caseid = user.ctx_case
    session['permissions'] = ac_get_effective_permissions_of_user(user)

    if caseid is None:
        case = Cases.query.order_by(Cases.case_id).first()
        user.ctx_case = case.case_id
        user.ctx_human_case = case.name
        db.session.commit()

    session['current_case'] = {
        'case_name': user.ctx_human_case,
        'case_info': "",
        'case_id': user.ctx_case
    }

    track_activity("user '{}' successfully logged-in".format(user), ctx_less=True, display_in_ui=False)
    return redirect(url_for('index.index', cid=user.ctx_case))