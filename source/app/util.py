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

import datetime
import decimal
import pickle
import random
import shutil
import string
import traceback
import weakref
import logging as log
from pathlib import Path

from flask_wtf import FlaskForm
from pyunpack import Archive

from flask import json, url_for, request, render_template
from flask_login import current_user
from sqlalchemy.ext.declarative import DeclarativeMeta
from werkzeug.utils import redirect

from functools import wraps

from app import app, db, TEMPLATE_PATH

# build a Json response
from app.datamgmt.case.case_db import get_case
from app.models import Cases


def response(msg, data):
    rsp = {
        "status": "success",
        "message": msg,
        "data": data if data is not None else []
    }
    return app.response_class(response=json.dumps(rsp),
                              status=200,
                              mimetype='application/json')


def response_error(msg, data=None, status=400):
    rsp = {
        "status": "error",
        "message": msg,
        "data": data if data is not None else []
    }
    return app.response_class(response=json.dumps(rsp),
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

    def cleanup_once_done(self, response, filepath):
        wr = weakref.ref(response, self._do_cleanup)
        self.weak_references[wr] = filepath

    def _do_cleanup(self, wr):
        filepath = self.weak_references[wr]
        shutil.rmtree(filepath, ignore_errors=True)


def get_urlcase(request):
    caseid = request.args.get('cid', default=None, type=int)
    redir = False
    if not caseid:
        try:

            js_d = request.get_json()
            if js_d:
                caseid = js_d.get('cid')
                request.json.pop('cid')
            else:
                caseid = current_user.ctx_case

        except Exception as e:
            cookie_session = request.cookies.get('session')
            if not cookie_session:
                # API, so just use the current_user context
                caseid = current_user.ctx_case

            else:
                log.error(traceback.print_exc())
                return True, None

        redir = True

    case = get_case(caseid)

    if not case:
        return True, None

    if caseid != current_user.ctx_case:
        current_user.ctx_case = case.case_id
        current_user.ctx_human_case = case.name
        db.session.commit()

    return redir, caseid


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


def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):

        if not current_user.is_authenticated:
            return redirect(url_for('login.login'))

        else:
            redir, caseid = get_urlcase(request=request)
            kwargs.update({"caseid": caseid, "url_redir": redir})

            return f(*args, **kwargs)

    return wrap


def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):

        if not current_user.is_authenticated:
            return redirect(url_for('login.login'))
        else:
            redir, caseid = get_urlcase(request=request)
            kwargs.update({"caseid": caseid, "url_redir": redir})

            roles = [role.name for role in current_user.roles]
            if "administrator" not in roles:
                return redirect(url_for('index.index'))

            else:
                return f(*args, **kwargs)

    return wrap


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

        if not current_user.is_authenticated:
            return response_error("Authentication required", status=401)

        else:
            redir, caseid = get_urlcase(request=request)
            if not caseid:
                return response_error("Invalid case ID", status=400)
            kwargs.update({"caseid": caseid})

            return f(*args, **kwargs)

    return wrap


def api_admin_required(f):
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

        if not current_user.is_authenticated:
            return response_error("Authentication required", status=401)

        else:
            redir, caseid = get_urlcase(request=request)
            if not caseid:
                return response_error("Invalid case ID", status=400)
            kwargs.update({"caseid": caseid})

            roles = [role.name for role in current_user.roles]
            if "administrator" not in roles:
                return response_error("Unauthorized", status=403)

            else:
                return f(*args, **kwargs)

    return wrap


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


# Set basic 404
@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    if request.content_type and 'application/json' in request.content_type:
        return response_error("Resource not found", status=404)

    return render_template('pages/error-404.html', template_folder=TEMPLATE_PATH)

