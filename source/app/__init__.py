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
import collections
import json
import logging as logger
import os
import urllib.parse
from flask import Flask
from flask import session
from flask_bcrypt import Bcrypt
from flask_caching import Cache
from flask_login import LoginManager
from flask_marshmallow import Marshmallow
from flask_socketio import SocketIO, Namespace
from flask_sqlalchemy import SQLAlchemy
from functools import partial
from sqlalchemy_imageattach.stores.fs import HttpExposedFileSystemStore
from werkzeug.middleware.proxy_fix import ProxyFix

from app.flask_dropzone import Dropzone
from app.iris_engine.tasker.celery import make_celery
from app.iris_engine.access_control.oidc_handler import get_oidc_client


class ReverseProxied(object):
    def __init__(self, flask_app):
        self._app = flask_app

    def __call__(self, environ, start_response):
        scheme = environ.get('HTTP_X_FORWARDED_PROTO', None)
        if scheme is not None:
            environ['wsgi.url_scheme'] = scheme
        return self._app(environ, start_response)


class AlertsNamespace(Namespace):
    pass


APP_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(APP_PATH, 'templates/')

# Grabs the folder where the script runs.
basedir = os.path.abspath(os.path.dirname(__file__))
LOG_FORMAT = '%(asctime)s :: %(levelname)s :: %(module)s :: %(funcName)s :: %(message)s'
LOG_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

logger.basicConfig(level=logger.INFO, format=LOG_FORMAT, datefmt=LOG_TIME_FORMAT)

app = Flask(__name__)


def ac_current_user_has_permission(*permissions):
    """
    Return True if current user has permission
    """
    for permission in permissions:

        if ('permissions' in session and
                session['permissions'] & permission.value == permission.value):
            return True

    return False


def ac_current_user_has_manage_perms():

    if session['permissions'] != 1 and session['permissions'] & 0x1FFFFF0 != 0:
        return True
    return False


app.jinja_env.filters['unquote'] = lambda u: urllib.parse.unquote(u)
app.jinja_env.filters['tojsonsafe'] = lambda u: json.dumps(u, indent=4, ensure_ascii=False)
app.jinja_env.filters['tojsonindent'] = lambda u: json.dumps(u, indent=4)
app.jinja_env.filters['escape_dots'] = lambda u: u.replace('.', '[.]')
app.jinja_env.globals.update(user_has_perm=ac_current_user_has_permission)
app.jinja_env.globals.update(user_has_manage_perms=ac_current_user_has_manage_perms)
app.jinja_options["autoescape"] = lambda _: True
app.jinja_env.autoescape = True

app.config.from_object('app.configuration.Config')

cache = Cache(app)

SQLALCHEMY_ENGINE_OPTIONS = {
    "json_deserializer": partial(json.loads, object_pairs_hook=collections.OrderedDict),
    "pool_pre_ping": True
}

db = SQLAlchemy(app, engine_options=SQLALCHEMY_ENGINE_OPTIONS)  # flask-sqlalchemy

bc = Bcrypt(app)  # flask-bcrypt

lm = LoginManager()  # flask-loginmanager
lm.init_app(app)  # init the login manager

ma = Marshmallow(app) # Init marshmallow

dropzone = Dropzone(app)

celery = make_celery(app)

store = HttpExposedFileSystemStore(
    path='images',
    prefix='/static/assets/images/'
)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.wsgi_app = store.wsgi_middleware(app.wsgi_app)

socket_io = SocketIO(app, cors_allowed_origins="*")

alerts_namespace = AlertsNamespace('/alerts')
socket_io.on_namespace(alerts_namespace)

oidc_client = None
if app.config.get('AUTHENTICATION_TYPE') == "oidc":
    oidc_client = get_oidc_client(app)

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()


from app import views
