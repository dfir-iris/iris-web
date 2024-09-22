#  IRIS Source Code
#  Copyright (C) 2022 - DFIR IRIS Team
#  contact@dfir-iris.org
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
import base64
import datetime
import decimal
import hashlib
import json
import jwt
import logging as log
import marshmallow
import pickle
import random
import requests
import shutil
import string
import traceback
import uuid
import weakref
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import hmac
from flask import Request
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask_login import current_user
from flask_login import login_user
from flask_wtf import FlaskForm
from functools import wraps
from jwt import PyJWKClient
from pathlib import Path
from pyunpack import Archive
from requests.auth import HTTPBasicAuth
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.utils import redirect

from app import TEMPLATE_PATH
from app import app
from app import db
from app.datamgmt.case.case_db import get_case
from app.datamgmt.manage.manage_access_control_db import user_has_client_access
from app.datamgmt.manage.manage_users_db import get_user
from app.iris_engine.access_control.utils import ac_fast_check_user_has_case_access
from app.iris_engine.access_control.utils import ac_get_effective_permissions_of_user
from app.iris_engine.utils.tracker import track_activity
from app.models import Cases
from app.models.authorization import CaseAccessLevel


def response(msg, data):
    rsp = {
        "status": "success",
        "message": msg,
        "data": data if data is not None else []
    }
    return app.response_class(response=json.dumps(rsp, cls=AlchemyEncoder),
                              status=200,
                              mimetype='application/json')


def response_error(msg, data=None, status=400):
    rsp = {
        "status": "error",
        "message": msg,
        "data": data if data is not None else []
    }
    return app.response_class(response=json.dumps(rsp, cls=AlchemyEncoder),
                              status=status,
                              mimetype='application/json')


def response_success(msg='', data=None):
    rsp = {
        "status": "success",
        "message": msg,
        "data": data if data is not None else []
    }
    return app.response_class(response=json.dumps(rsp, cls=AlchemyEncoder),
                              status=200,
                              mimetype='application/json')


def g_db_commit():
    db.session.commit()


def g_db_add(obj):
    if obj:
        db.session.add(obj)


def g_db_del(obj):
    if obj:
        db.session.delete(obj)


class PgEncoder(json.JSONEncoder):

    def default(self, o):
        if isinstance(o, datetime.datetime):
            return DictDatetime(o)

        if isinstance(o, decimal.Decimal):
            return str(o)

        return json.JSONEncoder.default(self, o)


class AlchemyEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj.__class__, DeclarativeMeta):
            # an SQLAlchemy class
            fields = {}
            for field in [x for x in dir(obj) if not x.startswith('_') and x != 'metadata'
                                                 and x != 'query' and x != 'query_class']:
                data = obj.__getattribute__(field)
                try:
                    json.dumps(data)  # this will fail on non-encodable values, like other classes
                    fields[field] = data
                except TypeError:
                    fields[field] = None
            # a json-encodable dict
            return fields

        if isinstance(obj, decimal.Decimal):
            return str(obj)

        if isinstance(obj, datetime.datetime) or isinstance(obj, datetime.date):
            return obj.isoformat()

        if isinstance(obj, uuid.UUID):
            return str(obj)

        else:
            if obj.__class__ == bytes:
                try:
                    return pickle.load(obj)
                except Exception:
                    return str(obj)

        return json.JSONEncoder.default(self, obj)


def DictDatetime(t):
    dl = ['Y', 'm', 'd', 'H', 'M', 'S', 'f']
    if type(t) is datetime.datetime:
        return {a: t.strftime('%{}'.format(a)) for a in dl}
    elif type(t) is dict:
        return datetime.datetime.strptime(''.join(t[a] for a in dl), '%Y%m%d%H%M%S%f')


def AlchemyFnCode(obj):
    """JSON encoder function for SQLAlchemy special classes."""
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    elif isinstance(obj, decimal.Decimal):
        return float(obj)


def return_task(success, user, initial, logs, data, case_name, imported_files):
    ret = {
        'success': success,
        'user': user,
        'initial': initial,
        'logs': logs,
        'data': data,
        'case_name': case_name,
        'imported_files': imported_files
    }
    return ret


def task_success(user=None, initial=None, logs=None, data=None, case_name=None, imported_files=None):
    return return_task(True, user, initial, logs, data, case_name, imported_files)


def task_failure(user=None, initial=None, logs=None, data=None, case_name=None, imported_files=None):
    return return_task(False, user, initial, logs, data, case_name, imported_files)


class FileRemover(object):
    def __init__(self):
        self.weak_references = dict()  # weak_ref -> filepath to remove

    def cleanup_once_done(self, response_d, filepath):
        wr = weakref.ref(response_d, self._do_cleanup)
        self.weak_references[wr] = filepath

    def _do_cleanup(self, wr):
        filepath = self.weak_references[wr]
        shutil.rmtree(filepath, ignore_errors=True)


def _get_caseid_from_request_data(request_data, no_cid_required):
    caseid = request_data.args.get('cid', default=None, type=int)
    if caseid:
        return False, caseid, True

    if no_cid_required:
        return False, caseid, True

    try:
        js_d = None

        if request_data.content_type == 'application/json':
            js_d = request_data.get_json()

        if not js_d:
            return _set_caseid_from_current_user()

        caseid = js_d.get('cid')
        request_data.json.pop('cid')

        return False, caseid, True

    except Exception as e:
        print(request_data.url)
        return _handle_exception(e, request_data)


def _set_caseid_from_current_user():
    redir = False
    if current_user.ctx_case is None:
        redir = True
        current_user.ctx_case = 1
    caseid = current_user.ctx_case
    return redir, caseid, True


def _handle_exception(e, request_data):
    cookie_session = request_data.cookies.get('session')
    if not cookie_session:
        return _set_caseid_from_current_user()

    log_exception_and_error(e)
    return True, 0, False


def log_exception_and_error(e):
    log.exception(e)
    log.error(traceback.print_exc())


def _handle_no_cid_required(no_cid_required):
    if no_cid_required:
        js_d = request.get_json(silent=True)
        caseid = None

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


def update_session(caseid, eaccess_level, from_api):
    if not from_api:
        restricted_access = ''
        if not eaccess_level:
            eaccess_level = [CaseAccessLevel.read_only, CaseAccessLevel.full_access]

        if CaseAccessLevel.read_only.value == eaccess_level:
            restricted_access = '<i class="ml-2 text-warning mt-1 fa-solid fa-lock" title="Read only access"></i>'

        update_current_case(caseid, restricted_access)


def update_current_case(caseid, restricted_access):
    if session['current_case']['case_id'] != caseid:
        case = get_case(caseid)
        if case:
            session['current_case'] = {
                'case_name': "{}".format(case.name),
                'case_info': "(#{} - {})".format(caseid, case.client.name),
                'case_id': caseid,
                'access': restricted_access
            }


def update_denied_case(caseid, from_api):
    if not from_api:
        session['current_case'] = {
            'case_name': "{} to #{}".format("Access denied", caseid),
            'case_info': "",
            'case_id': caseid,
            'access': '<i class="ml-2 text-danger mt-1 fa-solid fa-ban"></i>'
        }


def get_case_access(request_data, access_level, from_api=False, no_cid_required=False):
    redir, caseid, has_access = _get_caseid_from_request_data(request_data, no_cid_required)

    ctmp, has_access = _handle_no_cid_required(no_cid_required)
    redir = False
    if ctmp is not None:
        return redir, ctmp, has_access

    eaccess_level = ac_fast_check_user_has_case_access(current_user.id, caseid, access_level)
    if eaccess_level is None and access_level != []:
        update_denied_case(caseid, from_api)
        return redir, caseid, False

    update_session(caseid, eaccess_level, from_api)

    if caseid is not None and not get_case(caseid):
        log.warning('No case found. Using default case')
        return True, 1, True

    return redir, caseid, True


def get_urlcasename():
    caseid = request.args.get('cid', default=None, type=int)
    if not caseid:
        try:
            caseid = current_user.ctx_case
        except:
            return ["", ""]

    case = Cases.query.filter(Cases.case_id == caseid).first()

    if case is None:
        case_name = "CASE NOT FOUND"
        case_info = "Error"
    else:
        case_name = "{}".format(case.name)
        case_info = "(#{} - {})".format(caseid,
                                        case.client.name)

    return [case_name, case_info, caseid]


def _local_authentication_process(incoming_request: Request):
    return current_user.is_authenticated


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


def not_authenticated_redirection_url(request_url: str):
    redirection_mapper = {
        "oidc_proxy": lambda: app.config.get("AUTHENTICATION_PROXY_LOGOUT_URL"),
        "local": lambda: url_for('login.login', next=request_url),
        "ldap": lambda: url_for('login.login', next=request_url),
        "oidc": lambda: url_for('login.login', next=request_url),
    }

    return redirection_mapper.get(app.config.get("AUTHENTICATION_TYPE"))()


def is_user_authenticated(incoming_request: Request):
    authentication_mapper = {
        "oidc_proxy": _oidc_proxy_authentication_process,
        "local": _local_authentication_process,
        "ldap": _local_authentication_process,
        "oidc": _local_authentication_process,
    }

    return authentication_mapper.get(app.config.get("AUTHENTICATION_TYPE"))(incoming_request)


def is_authentication_local():
    return app.config.get("AUTHENTICATION_TYPE") == "local"


def is_authentication_ldap():
    return app.config.get('AUTHENTICATION_TYPE') == "ldap"


def is_authentication_oidc():
    return app.config.get('AUTHENTICATION_TYPE') == "oidc"


def regenerate_session():
    user_data = session.get('user_data', {})

    session.clear()

    session['user_data'] = user_data

    session.modified = True


def api_login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):

        if request.method == 'POST':
            cookie_session = request.cookies.get('session')
            if cookie_session:
                form = FlaskForm()
                if not form.validate():
                    return response_error('Invalid CSRF token')
                elif request.is_json:
                    request.json.pop('csrf_token')

        if not is_user_authenticated(request):
            return response_error("Authentication required", status=401)

        else:
            redir, caseid, access = get_case_access(request, [], from_api=True)
            if not caseid or redir:
                return response_error("Invalid case ID", status=404)
            kwargs.update({"caseid": caseid})

            return f(*args, **kwargs)

    return wrap


def ac_return_access_denied(caseid: int = None):
    error_uuid = uuid.uuid4()
    log.warning(f"Access denied to case #{caseid} for user ID {current_user.id}. Error {error_uuid}")
    return render_template('pages/error-403.html', user=current_user, caseid=caseid, error_uuid=error_uuid,
                           template_folder=TEMPLATE_PATH), 403


def ac_api_return_access_denied(caseid: int = None):
    error_uuid = uuid.uuid4()
    log.warning(f"EID {error_uuid} - Access denied with case #{caseid} for user ID {current_user.id} "
                f"accessing URI {request.full_path}")
    data = {
        'user_id': current_user.id,
        'case_id': caseid,
        'error_uuid': error_uuid
    }
    return response_error('Permission denied', data=data, status=403)


def ac_case_requires(*access_level):
    def inner_wrap(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            if not is_user_authenticated(request):
                return redirect(not_authenticated_redirection_url(request.full_path))

            else:
                redir, caseid, has_access = get_case_access(request, access_level)

                if not has_access:
                    return ac_return_access_denied(caseid=caseid)

                kwargs.update({"caseid": caseid, "url_redir": redir})

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
                    return ac_return_access_denied(caseid=0)

                access = ac_fast_check_user_has_case_access(current_user.id, case_id, access_level)
                if not access:
                    return ac_return_access_denied(caseid=case_id)

                return f(*args, **kwargs)

        return wrap
    return inner_wrap


def _user_has_required_permissions(permissions):
    if not permissions:
        return True

    for permission in permissions:
        # TODO do we really want to do this?
        #      as it is coded now, as soon as the user has one of the required
        #      permission, the action is allowed
        #      don't we rather want the user to have all required permissions?
        if session['permissions'] & permission.value:
            return True

    return False


def ac_requires(*permissions, no_cid_required=False):
    def inner_wrap(f):
        @wraps(f)
        def wrap(*args, **kwargs):

            if not is_user_authenticated(request):
                return redirect(not_authenticated_redirection_url(request.full_path))

            else:
                redir, caseid, _ = get_case_access(request, [], no_cid_required=no_cid_required)

                kwargs.update({"caseid": caseid, "url_redir": redir})

                if not _user_has_required_permissions(permissions):
                    return ac_return_access_denied()

                return f(*args, **kwargs)
        return wrap
    return inner_wrap


def ac_api_case_requires(*access_level):
    def inner_wrap(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            if request.method == 'POST':
                cookie_session = request.cookies.get('session')
                is_api = (request.headers.get('X-IRIS-AUTH') is not None) | (request.headers.get('Authorization') is not None)
                if cookie_session and not is_api:
                    form = FlaskForm()
                    if not form.validate():
                        return response_error('Invalid CSRF token')
                    elif request.is_json:
                        request.json.pop('csrf_token')

            if not is_user_authenticated(request):
                return response_error("Authentication required", status=401)

            else:
                redir, caseid, has_access = get_case_access(request, access_level, from_api=True)

                if not caseid or redir:
                    return response_error("Invalid case ID", status=404)

                if not has_access:
                    return ac_api_return_access_denied(caseid=caseid)

                kwargs.update({"caseid": caseid})

                return f(*args, **kwargs)

        return wrap
    return inner_wrap


def endpoint_deprecated(message, version):
    def inner_wrap(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            return response_error(f"Endpoint deprecated in {version}. {message}.", status=410)
        return wrap
    return inner_wrap


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


def ac_requires_client_access():
    def inner_wrap(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            client_id = kwargs.get('client_id')
            if not user_has_client_access(current_user.id, client_id):
                return ac_return_access_denied()

            return f(*args, **kwargs)
        return wrap
    return inner_wrap


def ac_requires_case_identifier():
    def decorate_with_requires_case_identifier(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            try:
                redir, caseid, _ = get_case_access(request, [], from_api=True)
            except Exception as e:
                log.exception(e)
                return response_error('Invalid data. Check server logs', status=500)

            if not caseid and not redir:
                return response_error('Invalid case ID', status=404)

            kwargs.update({'caseid': caseid})

            return f(*args, **kwargs)

        return wrap
    return decorate_with_requires_case_identifier


def ac_api_requires(*permissions):
    def inner_wrap(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            if request.method == 'POST':
                cookie_session = request.cookies.get('session')
                is_api = (request.headers.get('X-IRIS-AUTH') is not None) | (request.headers.get('Authorization') is not None)
                if cookie_session and not is_api:
                    form = FlaskForm()
                    if not form.validate():
                        return response_error('Invalid CSRF token')
                    elif request.is_json:
                        request.json.pop('csrf_token')

            if not is_user_authenticated(request):
                return response_error("Authentication required", status=401)

            if 'permissions' not in session:
                session['permissions'] = ac_get_effective_permissions_of_user(current_user)

            if not _user_has_required_permissions(permissions):
                return response_error('Permission denied', status=403)

            return f(*args, **kwargs)
        return wrap
    return inner_wrap


def decompress_7z(filename: Path, output_dir):
    """
    Decompress a 7z file in specified output directory
    :param filename: Filename to decompress
    :param output_dir: Target output dir
    :return: True if uncompress
    """
    try:
        a = Archive(filename=filename)
        a.extractall(directory=output_dir, auto_create_dir=True)

    except Exception as e:
        log.warning(e)
        return False

    return True


def get_random_suffix(length):
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str


def add_obj_history_entry(obj, action, commit=False):
    if hasattr(obj, 'modification_history'):

        if isinstance(obj.modification_history, dict):

            obj.modification_history.update({
                datetime.datetime.now().timestamp(): {
                    'user': current_user.user,
                    'user_id': current_user.id,
                    'action': action
                }
            })

        else:

            obj.modification_history = {
                datetime.datetime.now().timestamp(): {
                    'user': current_user.user,
                    'user_id': current_user.id,
                    'action': action
                }
            }
    flag_modified(obj, "modification_history")
    if commit:
        db.session.commit()

    return obj


# Set basic 404
@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    if request.content_type and 'application/json' in request.content_type:
        return response_error("Resource not found", status=404)

    return render_template('pages/error-404.html', template_folder=TEMPLATE_PATH), 404


def file_sha256sum(file_path):

    if not Path(file_path).is_file():
        return None

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

        return sha256_hash.hexdigest().upper()


def stream_sha256sum(stream):

    return hashlib.sha256(stream).hexdigest().upper()


@app.template_filter()
def format_datetime(value, frmt):
    return datetime.datetime.fromtimestamp(float(value)).strftime(frmt)


def hmac_sign(data):
    key = bytes(app.config.get("SECRET_KEY"), "utf-8")
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(data)
    signature = base64.b64encode(h.finalize())

    return signature


def hmac_verify(signature_enc, data):
    signature = base64.b64decode(signature_enc)
    key = bytes(app.config.get("SECRET_KEY"), "utf-8")
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(data)

    try:
        h.verify(signature)
        return True
    except InvalidSignature:
        return False


def str_to_bool(value):
    if value is None:
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return bool(value)

    return value.lower() in ['true', '1', 'yes', 'y', 't']


def assert_type_mml(input_var: any, field_name: str,  type: type, allow_none: bool = False,
                    max_len: int = None, max_val: int = None, min_val: int = None):
    if input_var is None:
        if allow_none is False:
            raise marshmallow.ValidationError("Invalid data - non null expected",
                                            field_name=field_name if field_name else "type")
        else:
            return True
    
    if isinstance(input_var, type):
        if max_len:
            if len(input_var) > max_len:
                raise marshmallow.ValidationError("Invalid data - max length exceeded",
                                                field_name=field_name if field_name else "type")

        if max_val:
            if input_var > max_val:
                raise marshmallow.ValidationError("Invalid data - max value exceeded",
                                                field_name=field_name if field_name else "type")

        if min_val:
            if input_var < min_val:
                raise marshmallow.ValidationError("Invalid data - min value exceeded",
                                                field_name=field_name if field_name else "type")

        return True
    
    try:

        if isinstance(type(input_var), type):
            return True

    except Exception as e:
        log.error(e)
        print(e)
        
    raise marshmallow.ValidationError("Invalid data type",
                                      field_name=field_name if field_name else "type")
