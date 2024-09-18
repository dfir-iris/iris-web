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
import uuid
from functools import wraps

from flask import request, session, render_template
from flask_login import current_user
from flask_wtf import FlaskForm
from werkzeug.utils import redirect

from app import TEMPLATE_PATH
from app.datamgmt.case.case_db import get_case
from app.datamgmt.manage.manage_access_control_db import user_has_client_access
from app.iris_engine.access_control.utils import ac_fast_check_user_has_case_access
from app.iris_engine.access_control.utils import ac_get_effective_permissions_of_user
from app.models.authorization import Permissions
from app.models.authorization import CaseAccessLevel
from app.util import update_current_case
from app.util import log_exception_and_error
from app.util import response_error
from app.util import is_user_authenticated
from app.util import not_authenticated_redirection_url
from app.util import ac_api_return_access_denied


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

        log_exception_and_error(e)
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


def _update_session(caseid, eaccess_level):
    restricted_access = ''
    if not eaccess_level:
        eaccess_level = [CaseAccessLevel.read_only, CaseAccessLevel.full_access]

    if CaseAccessLevel.read_only.value == eaccess_level:
        restricted_access = '<i class="ml-2 text-warning mt-1 fa-solid fa-lock" title="Read only access"></i>'

    update_current_case(caseid, restricted_access)


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

    eaccess_level = ac_fast_check_user_has_case_access(current_user.id, caseid, access_level)
    if eaccess_level is None and access_level:
        return redir, caseid, False

    if caseid is not None and not get_case(caseid):
        log.warning('No case found. Using default case')
        return True, 1, True

    return redir, caseid, True


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
