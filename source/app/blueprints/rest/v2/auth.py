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

import jwt
import pyotp

from flask import Blueprint
from flask import session
from flask import redirect
from flask import url_for
from flask import request
from flask import g
from flask_login import logout_user
from oic.oauth2.exception import GrantError

from app import app
from app import bc
from app.db import db
from app import oidc_client
from app.blueprints.iris_user import iris_current_user
from app.models.errors import ObjectNotFoundError
from app.logger import logger
from app.blueprints.access_controls import is_authentication_ldap
from app.blueprints.access_controls import is_authentication_oidc
from app.blueprints.access_controls import not_authenticated_redirection_url
from app.blueprints.rest.api_auth import api_auth
from app.blueprints.rest.endpoints import response_api_error, response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.business.auth import validate_ldap_login
from app.business.auth import validate_local_login
from app.business.users import users_get_active
from app.business.auth import generate_auth_tokens
from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import UserSchema


auth_blueprint = Blueprint('auth', __name__, url_prefix='/auth')


@auth_blueprint.post('/login')
def login():
    """
    Login endpoint. Handles taking user/pass combo and authenticating a local session or returning an error.
    """
    if iris_current_user.is_authenticated:
        logger.info('User already authenticated - redirecting')
        logger.debug(f'User {iris_current_user.user} already logged in')
        user = users_get_active(iris_current_user.id)
        result = UserSchema(exclude=['user_password', 'mfa_secrets', 'webauthn_credentials']).dump(user)
        return response_api_success(result)

    if is_authentication_oidc() and app.config.get('AUTHENTICATION_LOCAL_FALLBACK') is False:
        return redirect(url_for('login.oidc_login'))

    data = request.get_json(silent=True) or {}
    username = data.get('username')
    password = data.get('password')

    if is_authentication_ldap() is True:
        authed_user = validate_ldap_login(username, password, app.config.get('AUTHENTICATION_LOCAL_FALLBACK'))

    else:
        authed_user = validate_local_login(username, password)

    if authed_user is None:

        track_activity(f'User {username} tried to login. Invalid credentials', ctx_less=True, display_in_ui=False)
        return response_api_error('Invalid credentials')

    user_data = UserSchema(exclude=['user_password', 'mfa_secrets', 'webauthn_credentials']).dump(authed_user)

    # Generate auth tokens for API access
    tokens = generate_auth_tokens(authed_user)
    user_data.update({'tokens': tokens})

    track_activity(f'User {username} logged in', ctx_less=True, display_in_ui=False)
    return response_api_success(data=user_data)


@auth_blueprint.post('/mfa-setup')
def mfa_setup():
    """
    Persist user's MFA secret after validating:
      - refresh_token is valid (used to identify user_id)
      - provided TOTP token matches provided secret
      - provided password matches user (LDAP or local)
    """
    data = request.get_json(silent=True) or {}

    refresh_token = data.get('refresh_token')
    token = data.get('token')
    mfa_secret = data.get('mfa_secret')
    user_password = data.get('user_password') or data.get('password')

    if not refresh_token or not token or not mfa_secret or not user_password:
        return response_api_error('Missing required fields: refresh_token, token, mfa_secret, password')

    try:
        payload = jwt.decode(refresh_token, app.config.get('SECRET_KEY'), algorithms=['HS256'])

        if payload.get('type') != 'refresh':
            return response_api_error('Invalid token type')

        user_id = payload.get('user_id')
        user = users_get_active(user_id)

        totp = pyotp.TOTP(mfa_secret)
        if not totp.verify(str(token)):
            track_activity(
                f"Failed MFA setup for user {user.user}. Invalid token.",
                ctx_less=True,
                display_in_ui=False,
            )
            return response_api_error('Invalid token')

        has_valid_password = False

        if is_authentication_ldap() is True:
            if validate_ldap_login(
                user.user,
                user_password,
                local_fallback=app.config.get("AUTHENTICATION_LOCAL_FALLBACK"),
            ):
                has_valid_password = True
        else:
            if bc.check_password_hash(user.password, user_password):
                has_valid_password = True

        if not has_valid_password:
            track_activity(
                f"Failed MFA setup for user {user.user}. Invalid password.",
                ctx_less=True,
                display_in_ui=False,
            )
            return response_api_error('Invalid password')

        user.mfa_secrets = mfa_secret
        user.mfa_setup_complete = True
        db.session.commit()

        track_activity(
            f"MFA setup successful for user {user.user}",
            ctx_less=True,
            display_in_ui=False,
        )

        return response_api_success({'mfa_setup_complete': True})

    except ObjectNotFoundError:
        return response_api_not_found()
    except jwt.ExpiredSignatureError:
        return response_api_error('Refresh token has expired')
    except jwt.InvalidTokenError:
        return response_api_error('Invalid refresh token')


@auth_blueprint.post('/mfa-verify')
def mfa_verify():
    """
    Verify a TOTP token against the saved MFA secret.
    Uses refresh_token to identify the user (no reliance on iris_current_user).
    """
    data = request.get_json(silent=True) or {}

    refresh_token = data.get('refresh_token')
    token = data.get('token')

    if not refresh_token or not token:
        return response_api_error('Missing required fields: refresh_token, token')

    try:
        payload = jwt.decode(refresh_token, app.config.get('SECRET_KEY'), algorithms=['HS256'])

        if payload.get('type') != 'refresh':
            return response_api_error('Invalid token type')

        user_id = payload.get('user_id')
        user = users_get_active(user_id)

        if not user.mfa_secrets or not user.mfa_setup_complete:
            return response_api_error('MFA setup required')

        totp = pyotp.TOTP(user.mfa_secrets)
        if not totp.verify(str(token), valid_window=1):
            track_activity(
                f"Failed MFA verification for user {user.user}. Invalid token.",
                ctx_less=True,
                display_in_ui=False,
            )
            return response_api_error('Invalid token')

        track_activity(
            f"MFA verification successful for user {user.user}",
            ctx_less=True,
            display_in_ui=False,
        )

        tokens = generate_auth_tokens(user, mfa_verified=True)

        return response_api_success({'mfa_verified': True, 'tokens': tokens})

    except ObjectNotFoundError:
        return response_api_not_found()
    except jwt.ExpiredSignatureError:
        return response_api_error('Refresh token has expired')
    except jwt.InvalidTokenError:
        return response_api_error('Invalid refresh token')


@auth_blueprint.get('/whoami')
@api_auth()
def whoami():
    """
    Returns current authenticated user info (based on the existing session) and API tokens.
    Output shape matches the frontend's existing local-login handler:
      { responseData, tokenInfo, redirectTo }
    """
    user = g.api_user

    response_data = UserSchema(
        exclude=['user_password', 'mfa_secrets', 'webauthn_credentials']
    ).dump(user)

    return response_api_success(data={
        'responseData': response_data,
        'tokenInfo': None,
        'redirectTo': '/'
    })


@auth_blueprint.post('/logout')
@api_auth()
def logout():
    """
    Logout function. Erase its session and redirect to index i.e login
    :return: Page
    """

    if session.get('current_case'):
        iris_current_user.ctx_case = session['current_case']['case_id']
        db.session.commit()

    if is_authentication_oidc():
        if oidc_client.provider_info.get('end_session_endpoint'):
            try:
                logout_request = oidc_client.construct_EndSessionRequest(
                    state=session['oidc_state'])
                logout_url = logout_request.request(
                    oidc_client.provider_info["end_session_endpoint"])
                track_activity(f'user \'{iris_current_user.user}\' has been logged-out',
                               ctx_less=True, display_in_ui=False)
                logout_user()
                session.clear()
                return redirect(logout_url)
            except GrantError:
                track_activity(
                    f'no oidc session found for user \'{iris_current_user.user}\', skipping oidc provider logout and continuing to logout local user',
                    ctx_less=True,
                    display_in_ui=False
                )

    track_activity(f'user \'{iris_current_user.user}\' has been logged-out',
                   ctx_less=True, display_in_ui=False)
    logout_user()
    session.clear()

    return redirect(not_authenticated_redirection_url('/'))


@auth_blueprint.post('/refresh-token')
def refresh_token_endpoint():
    """
    Refresh authentication tokens using a valid refresh token
    """
    data = request.get_json(silent=True) or {}
    refresh_token = data.get('refresh_token')
    if not refresh_token:
        return response_api_error('Refresh token is required')

    try:
        # Decode the token manually to check the type
        payload = jwt.decode(refresh_token, app.config.get('SECRET_KEY'), algorithms=['HS256'])

        # Verify it's a refresh token
        if payload.get('type') != 'refresh':
            return response_api_error('Invalid token type')

        user_id = payload.get('user_id')
        user = users_get_active(user_id)

        # Generate new tokens
        new_tokens = generate_auth_tokens(user)

        return response_api_success({'tokens': new_tokens})

    except ObjectNotFoundError:
        return response_api_not_found()
    except jwt.ExpiredSignatureError:
        return response_api_error('Refresh token has expired')
    except jwt.InvalidTokenError:
        return response_api_error('Invalid refresh token')
