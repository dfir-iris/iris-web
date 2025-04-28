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

from urllib.parse import urlparse, urljoin

from flask import session
from flask import redirect
from flask import url_for
from flask import request
from flask_login import login_user

from app import bc
from app import app
from app import db
from app.logger import logger
from app.business.users import retrieve_user_by_username
from app.datamgmt.manage.manage_srv_settings_db import get_server_settings_as_dict
from app.datamgmt.manage.manage_users_db import get_active_user
from app.iris_engine.access_control.ldap_handler import ldap_authenticate
from app.iris_engine.access_control.utils import ac_get_effective_permissions_of_user
from app.iris_engine.utils.tracker import track_activity
from app.models.cases import Cases
from app.schema.marshables import UserSchema

import datetime
import jwt


def return_authed_user_info(user_id):
    """
    Return the user object by user id.

    :param user_id: User ID
    :return: User object if found, None otherwise
    """
    user = get_active_user(user_id=user_id)
    if not user:
        return None

    return UserSchema(exclude=['user_password', 'mfa_secrets', 'webauthn_credentials']).dump(user)


def validate_ldap_login(username: str, password: str, local_fallback: bool = True):
    """
    Validate the user login using LDAP authentication.

    :param username: Username
    :param password: Password
    :param local_fallback: If True, will fall back to local authentication if LDAP fails.
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

        user = retrieve_user_by_username(username)
        if not user:
            return None

        user_data = UserSchema(exclude=['user_password', 'mfa_secrets', 'webauthn_credentials']).dump(user)

        # Generate auth tokens for API access
        tokens = generate_auth_tokens(user)
        user_data.update({'tokens': tokens})

        return user_data
    except Exception as e:
        logger.error(e.__str__())
        return None


def validate_local_login(username: str, password: str):
    """
    Validate the user login using local authentication.

    :param username: Username
    :param password: Password

    :return: User object if successful, None otherwise
    """
    user = retrieve_user_by_username(username)
    if not user:
        return None

    if bc.check_password_hash(user.password, password):
        wrap_login_user(user)

        user_data = UserSchema(exclude=['user_password', 'mfa_secrets', 'webauthn_credentials']).dump(user)

        # Generate auth tokens for API access
        tokens = generate_auth_tokens(user)
        user_data.update({'tokens': tokens})

        return user_data

    track_activity(f'wrong login password for user \'{username}\' using local auth', ctx_less=True, display_in_ui=False)
    return None


def _is_safe_url(target):
    """
    Check whether the target URL is safe for redirection by ensuring that it is either a relative URL or
    has the same host as the current request.
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def _filter_next_url(next_url, context_case):
    """
    Ensures that the URL to which the user is redirected is safe. If the provided URL is not safe or is missing,
    a default URL (typically the index page) is returned.
    """
    if not next_url:
        return url_for('index.index', cid=context_case)
    # Remove backslashes to mitigate obfuscation
    next_url = next_url.replace('\\', '')
    if _is_safe_url(next_url):
        return next_url
    return url_for('index.index', cid=context_case)


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

    next_url = _filter_next_url(request.args.get('next'), user.ctx_case)
    return redirect(next_url)


def generate_auth_tokens(user):
    """
    Generate access and refresh tokens with essential user data

    :param user: User object
    :return: Dict containing tokens with expiry
    """
    # Configure token expiration times
    access_token_expiry = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        minutes=app.config.get('ACCESS_TOKEN_EXPIRES_MINUTES', 15)
    )
    refresh_token_expiry = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        days=app.config.get('REFRESH_TOKEN_EXPIRES_DAYS', 14)
    )

    # Generate access token with user data
    access_token_payload = {
        'user_id': user.id,
        'username': user.name,
        'user_email': user.email,
        'user_login': user.user,
        'exp': access_token_expiry
    }
    access_token = jwt.encode(
        access_token_payload,
        app.config.get('SECRET_KEY'),
        algorithm='HS256'
    )

    # Generate refresh token
    refresh_token_payload = {
        'user_id': user.id,
        'username': user.name,
        'user_email': user.email,
        'user_login': user.user,
        'exp': refresh_token_expiry,
        'type': 'refresh'
    }
    refresh_token = jwt.encode(
        refresh_token_payload,
        app.config.get('SECRET_KEY'),
        algorithm='HS256'
    )

    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'access_token_expires_at': access_token_expiry.timestamp(),
        'refresh_token_expires_at': refresh_token_expiry.timestamp()
    }


def validate_auth_token(token):
    """
    Validate an authentication token

    :param token: JWT token to validate
    :return: Dict with user data if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, app.config.get('SECRET_KEY'), algorithms=['HS256'])
        return {
            'user_id': payload.get('user_id'),
            'username': payload.get('username')
        }
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
