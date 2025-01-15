#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

from urllib.parse import urlsplit

from flask import session, redirect, url_for, request
from flask_login import login_user

from app import bc, app, db
from app.datamgmt.manage.manage_srv_settings_db import get_server_settings_as_dict
from app.datamgmt.manage.manage_users_db import get_active_user_by_login
from app.iris_engine.access_control.ldap_handler import ldap_authenticate
from app.iris_engine.access_control.utils import ac_get_effective_permissions_of_user
from app.iris_engine.utils.tracker import track_activity
from app.models.cases import Cases
from app.schema.marshables import UserSchema

log = app.logger

def _retrieve_user_by_username(username:str):
    """
    Retrieve the user object by username.

    :param username: Username
    :return: User object if found, None
    """
    user = get_active_user_by_login(username)
    if not user:
        track_activity(f'someone tried to log in with user \'{username}\', which does not exist',
                       ctx_less=True, display_in_ui=False)
    return user

def validate_ldap_login(username: str, password:str, local_fallback: bool = True):
    """
    Validate the user login using LDAP authentication.

    :param username: Username
    :param password: Password
    :param local_fallback: If True, will fallback to local authentication if LDAP fails.
    :return: User object if successful, None otherwise
    """
    try:
        if ldap_authenticate(username, password) is False:
            if local_fallback is True:
                track_activity(f'wrong login password for user \'{username}\' using LDAP auth - falling back to local based on settings',
                               ctx_less=True, display_in_ui=False)
                return validate_local_login(username, password)
            track_activity(f'wrong login password for user \'{username}\' using LDAP auth', ctx_less=True, display_in_ui=False)
            return None

        user = _retrieve_user_by_username(username)
        if not user:
            return None

        return UserSchema(exclude=['user_password', 'mfa_secrets', 'webauthn_credentials']).dump(user)
    except Exception as e:
        log.error(e.__str__())
        return None


def validate_local_login(username: str, password: str):
    """
    Validate the user login using local authentication.

    :param username: Username
    :param password: Password

    :return: User object if successful, None otherwise
    """
    user = _retrieve_user_by_username(username)
    if not user:
        return None

    if bc.check_password_hash(user.password, password):
        wrap_login_user(user)
        return UserSchema(exclude=['user_password', 'mfa_secrets', 'webauthn_credentials']).dump(user)

    track_activity(f'wrong login password for user \'{username}\' using local auth', ctx_less=True, display_in_ui=False)
    return None


def wrap_login_user(user, is_oidc=False):

    session['username'] = user.user

    if 'SERVER_SETTINGS' not in app.config:
        app.config['SERVER_SETTINGS'] = get_server_settings_as_dict()

    if app.config['SERVER_SETTINGS']['enforce_mfa'] is True and is_oidc is False:
        if "mfa_verified" not in session or session["mfa_verified"] is False:
            return redirect(url_for('mfa_verify'))

    login_user(user)

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

    track_activity(f'user \'{user.user}\' successfully logged-in', ctx_less=True, display_in_ui=False)

    next_url = None
    if request.args.get('next'):
        next_url = request.args.get('next') if 'cid=' in request.args.get('next') else request.args.get('next') + '?cid=' + str(user.ctx_case)

    if not next_url or urlsplit(next_url).netloc != '':
        next_url = url_for('index.index', cid=user.ctx_case)

    return redirect(next_url)