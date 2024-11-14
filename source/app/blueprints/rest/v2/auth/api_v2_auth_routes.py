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

from flask import Blueprint, redirect, url_for
from flask import request
from flask_login import current_user

from app import app
from app.blueprints.access_controls import ac_api_requires, is_authentication_oidc, is_authentication_ldap
from app.blueprints.pages.login.login_routes import _authenticate_ldap
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_not_found
from app.business.auth import validate_ldap_login, validate_local_login
from app.business.cases import cases_exists
from app.business.assets import assets_create
from app.business.assets import assets_delete
from app.business.assets import assets_get
from app.business.errors import BusinessProcessingError
from app.business.errors import ObjectNotFoundError
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import CaseAssetsSchema
from app.blueprints.access_controls import ac_api_return_access_denied

api_v2_auth_blueprint = Blueprint('auth_rest_v2',
                                    __name__,
                                    url_prefix='/api/v2')

@api_v2_auth_blueprint.route('/auth/login', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return response_api_success('User already authenticated')

    if is_authentication_oidc() and app.config.get('AUTHENTICATION_LOCAL_FALLBACK') is False:
        return redirect(url_for('login.oidc_login'))

    username = request.json.get('username')
    password = request.json.get('password')

    if is_authentication_ldap() is True:
        authed_user = validate_ldap_login(username, password, app.config.get('AUTHENTICATION_LOCAL_FALLBACK'))

    else:
        authed_user = validate_local_login(username, password)

    if authed_user is None:
        return response_api_error('Invalid credentials')

    return response_api_success(data=authed_user)