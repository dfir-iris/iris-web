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

import json
import logging as log
import traceback
import uuid
from functools import wraps

import jwt
import requests

from flask import Request
from flask import url_for
from flask import request
from flask import render_template
from flask import session
from flask_login import current_user
from flask_login import login_user
from flask_wtf import FlaskForm
from jwt import PyJWKClient
from requests.auth import HTTPBasicAuth
from werkzeug.utils import redirect

from app import TEMPLATE_PATH

from app import app
from app import db
from app.blueprints.responses import response_error
from app.datamgmt.case.case_db import get_case
from app.datamgmt.manage.manage_access_control_db import user_has_client_access
from app.datamgmt.manage.manage_users_db import get_user
from app.iris_engine.access_control.utils import ac_fast_check_user_has_case_access
from app.iris_engine.access_control.utils import ac_get_effective_permissions_of_user
from app.iris_engine.utils.tracker import track_activity
from app.models.cases import Cases
from app.models.authorization import Permissions
from app.models.authorization import CaseAccessLevel


def _user_has_at_least_a_required_permission(permissions: list[Permissions]):
    """
        Returns true as soon as the user has at least one permission in the list of permissions
        Returns true if the list of required permissions is empty
    """
    if not permissions:
        return True

    for permission in permissions:
        if session['permissions'] & permission.value:
            return True

    return False


def _set_caseid_from_current_user():
    redir = False
    if current_user.ctx_case is None:
        redir = True
        current_user.ctx_case = 1
    caseid = current_user.ctx_case
    return redir, caseid


def _log_exception_and_error(e):
    log.exception(e)
    log.error(traceback.print_exc())


def _get_caseid_from_request_data(request_data, no_cid_required):
    caseid = request_data.args.get('cid', default=None, type=int)
    if caseid:
        return False, caseid, True

    if no_cid_required:
        return False, caseid, True

    js_d = None

    try:
        if request_data.content_type == 'application/json':
            js_d = request_data.get_json()

        if not js_d:
            redir, caseid = _set_caseid_from_current_user()
            return redir, caseid, True

        if 'cid' not in js_d:
            cookie_session = request_data.cookies.get('session')
            if not cookie_session:
                redir, caseid = _set_caseid_from_current_user()
                return redir, caseid, True

        caseid = js_d.get('cid')

        return False, caseid, True

    except Exception as e:
        cookie_session = request_data.cookies.get('session')
        if not cookie_session:
            redir, caseid = _set_caseid_from_current_user()
            return redir, caseid, True

        _log_exception_and_error(e)
        return True, 0, False


def _handle_no_cid_required(no_cid_required):
    if no_cid_required:
        js_d = request.get_json(silent=True)

        try:

            if type(js_d) == str:
                js_d = json.loads(js_d)

            caseid = js_d.get('cid') if type(js_d) == dict else None
            if caseid and 'cid' in request.json:
                request.json.pop('cid')

        except Exception:
            return None, False

        return caseid, True

    return None, False


def _update_denied_case(caseid):
    session['current_case'] = {
        'case_name': "{} to #{}".format("Access denied", caseid),
        'case_info': "",
        'case_id': caseid,
        'access': '<i class="ml-2 text-danger mt-1 fa-solid fa-ban"></i>'
    }


def _update_current_case(caseid, restricted_access):
    if session['current_case']['case_id'] != caseid:
        case = get_case(caseid)
        if case:
            session['current_case'] = {
                'case_name': "{}".format(case.name),
                'case_info': "(#{} - {})".format(caseid, case.client.name),
                'case_id': caseid,
                'access': restricted_access
            }


def _update_session(caseid, eaccess_level):
    restricted_access = ''
    if not eaccess_level:
        eaccess_level = [CaseAccessLevel.read_only, CaseAccessLevel.full_access]

    if CaseAccessLevel.read_only.value == eaccess_level:
        restricted_access = '<i class="ml-2 text-warning mt-1 fa-solid fa-lock" title="Read only access"></i>'

    _update_current_case(caseid, restricted_access)


# TODO would be nice to remove parameter no_cid_required
def _get_case_access(request_data, access_level, no_cid_required=False):
    redir, caseid, has_access = _get_caseid_from_request_data(request_data, no_cid_required)

    ctmp, has_access = _handle_no_cid_required(no_cid_required)
    redir = False
    if ctmp is not None:
        return redir, ctmp, has_access

    eaccess_level = ac_fast_check_user_has_case_access(current_user.id, caseid, access_level)
    if eaccess_level is None and access_level:
        _update_denied_case(caseid)
        return redir, caseid, False

    _update_session(caseid, eaccess_level)

    if caseid is not None and not get_case(caseid):
        log.warning('No case found. Using default case')
        return True, 1, True

    return redir, caseid, True


def _is_csrf_token_valid():
    if request.method != 'POST':
        return True
    if request.headers.get('X-IRIS-AUTH') is not None:
        return True
    if request.headers.get('Authorization') is not None:
        return True
    cookie_session = request.cookies.get('session')
    # True in the absence of a session cookie, because no CSRF token is required for API calls
    if not cookie_session:
        return True
    form = FlaskForm()
    if not form.validate():
        return False
    # TODO not nice to have a side-effect within a 'is' method.
    if request.is_json:
        request.json.pop('csrf_token')
    return True


def _ac_return_access_denied(caseid: int = None):
    error_uuid = uuid.uuid4()
    log.warning(f"Access denied to case #{caseid} for user ID {current_user.id}. Error {error_uuid}")
    return render_template('pages/error-403.html', user=current_user, caseid=caseid, error_uuid=error_uuid,
                           template_folder=TEMPLATE_PATH), 403


def ac_requires_case_identifier(*access_level):
    def decorate_with_requires_case_identifier(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            try:
                redir, caseid, has_access = get_case_access_from_api(request, access_level)
            except Exception as e:
                log.exception(e)
                return response_error('Invalid data. Check server logs', status=500)

            if not caseid and not redir:
                return response_error('Invalid case ID', status=404)

            if not has_access:
                return ac_api_return_access_denied(caseid=caseid)

            kwargs.update({'caseid': caseid})

            return f(*args, **kwargs)

        return wrap
    return decorate_with_requires_case_identifier


def get_case_access_from_api(request_data, access_level):
    redir, caseid, has_access = _get_caseid_from_request_data(request_data, False)
    redir = False

    if not hasattr(current_user, 'id'):
        # Anonymous request, deny access
        return False, 1, False

    eaccess_level = ac_fast_check_user_has_case_access(current_user.id, caseid, access_level)
    if eaccess_level is None and access_level:
        return redir, caseid, False

    if caseid is not None and not get_case(caseid):
        log.warning('No case found. Using default case')
        return True, 1, True

    return redir, caseid, True


def not_authenticated_redirection_url(request_url: str):
    redirection_mapper = {
        "oidc_proxy": lambda: app.config.get("AUTHENTICATION_PROXY_LOGOUT_URL"),
        "local": lambda: url_for('login.login', next=request_url),
        "ldap": lambda: url_for('login.login', next=request_url),
        "oidc": lambda: url_for('login.login', next=request_url,)
    }

    return redirection_mapper.get(app.config.get("AUTHENTICATION_TYPE"))()


def ac_case_requires(*access_level):
    def inner_wrap(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            if not is_user_authenticated(request):
                return redirect(not_authenticated_redirection_url(request.full_path))

            redir, caseid, has_access = _get_case_access(request, access_level)

            if not has_access:
                return _ac_return_access_denied(caseid=caseid)

            kwargs.update({"caseid": caseid, "url_redir": redir})

            return f(*args, **kwargs)

        return wrap
    return inner_wrap


# TODO try to remove option no_cid_required
def ac_requires(*permissions, no_cid_required=False):
    def inner_wrap(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            if not is_user_authenticated(request):
                return redirect(not_authenticated_redirection_url(request.full_path))

            redir, caseid, _ = _get_case_access(request, [], no_cid_required=no_cid_required)
            kwargs.update({'caseid': caseid, 'url_redir': redir})

            if not _user_has_at_least_a_required_permission(permissions):
                return _ac_return_access_denied()

            return f(*args, **kwargs)
        return wrap
    return inner_wrap


def ac_api_requires(*permissions):
    def inner_wrap(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            if not _is_csrf_token_valid():
                return response_error('Invalid CSRF token')

            if not is_user_authenticated(request):
                return response_error('Authentication required', status=401)

            if 'permissions' not in session:
                session['permissions'] = ac_get_effective_permissions_of_user(current_user)

            if not _user_has_at_least_a_required_permission(permissions):
                return response_error('Permission denied', status=403)

            return f(*args, **kwargs)
        return wrap
    return inner_wrap


def ac_requires_client_access():
    def inner_wrap(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            client_id = kwargs.get('client_id')
            if not user_has_client_access(current_user.id, client_id):
                return _ac_return_access_denied()

            return f(*args, **kwargs)
        return wrap
    return inner_wrap


def ac_socket_requires(*access_level):
    def inner_wrap(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            if not is_user_authenticated(request):
                return redirect(not_authenticated_redirection_url(request.full_path))

            else:
                chan_id = args[0].get('channel')
                if chan_id:
                    case_id = int(chan_id.replace('case-', '').split('-')[0])
                else:
                    return _ac_return_access_denied(caseid=0)

                access = ac_fast_check_user_has_case_access(current_user.id, case_id, access_level)
                if not access:
                    return _ac_return_access_denied(caseid=case_id)

                return f(*args, **kwargs)

        return wrap
    return inner_wrap


def ac_api_return_access_denied(caseid: int = None):
    user_id = current_user.id if hasattr(current_user, 'id') else 'Anonymous'
    error_uuid = uuid.uuid4()
    log.warning(f"EID {error_uuid} - Access denied with case #{caseid} for user ID {user_id} "
                f"accessing URI {request.full_path}")
    data = {
        'user_id': user_id,
        'case_id': caseid,
        'error_uuid': error_uuid
    }
    return response_error('Permission denied', data=data, status=403)


def ac_api_requires_client_access():
    def inner_wrap(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            client_id = kwargs.get('client_id')
            if not user_has_client_access(current_user.id, client_id):
                return response_error("Permission denied", status=403)

            return f(*args, **kwargs)
        return wrap
    return inner_wrap


def _authenticate_with_email(user_email):
    user = get_user(user_email, id_key="email")
    if not user:
        log.error(f'User with email {user_email} is not registered in the IRIS')
        return False

    login_user(user)
    track_activity(f"User '{user.id}' successfully logged-in", ctx_less=True)

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

    return True


def _oidc_proxy_authentication_process(incoming_request: Request):
    # Get the OIDC JWT authentication token from the request header
    authentication_token = incoming_request.headers.get('X-Forwarded-Access-Token', '')

    if app.config.get("AUTHENTICATION_TOKEN_VERIFY_MODE") == 'lazy':
        user_email = incoming_request.headers.get('X-Email')

        if user_email:
            return _authenticate_with_email(user_email.split(',')[0])

    elif app.config.get("AUTHENTICATION_TOKEN_VERIFY_MODE") == 'introspection':
        # Use the authentication server's token introspection endpoint in order to determine if the request is valid /
        # authenticated. The TLS_ROOT_CA is used to validate the authentication server's certificate.
        # The other solution was to skip the certificate verification, BUT as the authentication server might be
        # located on another server, this check is necessary.

        introspection_body = {"token": authentication_token}
        introspection = requests.post(
            app.config.get("AUTHENTICATION_TOKEN_INTROSPECTION_URL"),
            auth=HTTPBasicAuth(app.config.get('AUTHENTICATION_CLIENT_ID'), app.config.get('AUTHENTICATION_CLIENT_SECRET')),
            data=introspection_body,
            verify=app.config.get("TLS_ROOT_CA")
        )
        if introspection.status_code == 200:
            response_json = introspection.json()

            if response_json.get("active", False) is True:
                user_email = response_json.get("sub")
                return _authenticate_with_email(user_email=user_email)

            else:
                log.info("USER IS NOT AUTHENTICATED")
                return False

    elif app.config.get("AUTHENTICATION_TOKEN_VERIFY_MODE") == 'signature':
        # Use the JWKS urls provided by the OIDC discovery to fetch the signing keys
        # and check the signature of the token
        try:
            jwks_client = PyJWKClient(app.config.get("AUTHENTICATION_JWKS_URL"))
            signing_key = jwks_client.get_signing_key_from_jwt(authentication_token)

            try:

                data = jwt.decode(
                    authentication_token,
                    signing_key.key,
                    algorithms=["RS256"],
                    audience=app.config.get("AUTHENTICATION_AUDIENCE"),
                    options={"verify_exp": app.config.get("AUTHENTICATION_VERIFY_TOKEN_EXP")},
                )

            except jwt.ExpiredSignatureError:
                log.error("Provided token has expired")
                return False

        except Exception as e:
            log.error(f"Error decoding JWT. {e.__str__()}")
            return False

        # Extract the user email
        user_email = data.get("sub")

        return _authenticate_with_email(user_email)

    else:
        log.error("ERROR DURING TOKEN INTROSPECTION PROCESS")
        return False


def _local_authentication_process(incoming_request: Request):
    return current_user.is_authenticated


def is_user_authenticated(incoming_request: Request):
    authentication_mapper = {
        "oidc_proxy": _oidc_proxy_authentication_process,
        "local": _local_authentication_process,
        "ldap": _local_authentication_process,
        "oidc": _local_authentication_process,
    }

    return authentication_mapper.get(app.config.get("AUTHENTICATION_TYPE"))(incoming_request)


def is_authentication_oidc():
    return app.config.get('AUTHENTICATION_TYPE') == "oidc"


def is_authentication_ldap():
    return app.config.get('AUTHENTICATION_TYPE') == "ldap"
