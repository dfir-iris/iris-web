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

from flask import Blueprint, session
from flask import redirect, url_for
from flask import request
from flask_login import current_user, logout_user
from oic.oauth2.exception import GrantError

from app import app
from app import db
from app import oidc_client
from app.blueprints.access_controls import is_authentication_ldap
from app.blueprints.access_controls import is_authentication_oidc
from app.blueprints.access_controls import not_authenticated_redirection_url
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.business.auth import validate_ldap_login, validate_local_login
from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import UserSchema


auth_blueprint = Blueprint('auth', __name__, url_prefix='/auth')


# TODO put this endpoint back after thinking about it (doesn't feel REST)
#@auth_blueprint.post('/login')
def login():
    """
    Login endpoint. Handles taking user/pass combo and authenticating a local session or returning an error.
    """

    if current_user.is_authenticated:
        return response_api_success('User already authenticated')

    if is_authentication_oidc() and app.config.get('AUTHENTICATION_LOCAL_FALLBACK') is False:
        return redirect(url_for('login.oidc_login'))

    username = request.json.get('username')
    password = request.json.get('password')

    if is_authentication_ldap() is True:
        authed_user = validate_ldap_login(
            username, password, app.config.get('AUTHENTICATION_LOCAL_FALLBACK'))

    else:
        authed_user = validate_local_login(username, password)

    if authed_user is None:
        return response_api_error('Invalid credentials')

    return response_api_success(data=authed_user)


# TODO put this endpoint back after thinking about it (doesn't feel REST)
#@auth_blueprint.get('/logout')
def logout():
    """
    Logout function. Erase its session and redirect to index i.e login
    :return: Page
    """

    if session['current_case']:
        current_user.ctx_case = session['current_case']['case_id']
        current_user.ctx_human_case = session['current_case']['case_name']
        db.session.commit()

    if is_authentication_oidc():
        if oidc_client.provider_info.get("end_session_endpoint"):
            try:
                logout_request = oidc_client.construct_EndSessionRequest(
                    state=session["oidc_state"])
                logout_url = logout_request.request(
                    oidc_client.provider_info["end_session_endpoint"])
                track_activity("user '{}' has been logged-out".format(
                    current_user.user), ctx_less=True, display_in_ui=False)
                logout_user()
                session.clear()
                return redirect(logout_url)
            except GrantError:
                track_activity(
                    f"no oidc session found for user '{current_user.user}', skipping oidc provider logout and continuing to logout local user",
                    ctx_less=True,
                    display_in_ui=False
                )

    track_activity("user '{}' has been logged-out".format(current_user.user),
                   ctx_less=True, display_in_ui=False)
    logout_user()
    session.clear()

    return redirect(not_authenticated_redirection_url('/'))


# TODO shouldn't we rather have /api/v2/users/{identifier}?
#@auth_blueprint.route('/whoami', methods=['GET'])
def whoami():
    """
    Returns information about the currently authenticated user.
    """

    # Ensure we are authenticated
    if not current_user.is_authenticated:
        return response_api_error("Unauthenticated")

    # Return the current_user dict
    return response_api_success(data=UserSchema(only=[
        'id', 'user_name', 'user_login', 'user_email'
    ]).dump(current_user))
