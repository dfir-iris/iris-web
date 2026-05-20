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

import os
from flask import Flask
from flask import g
from flask import session
from flask_bcrypt import Bcrypt
from flask_caching import Cache
from flask_cors import CORS

from flask_login import LoginManager
from flask_marshmallow import Marshmallow
from flask_socketio import SocketIO
from flask_socketio import Namespace

from werkzeug.middleware.proxy_fix import ProxyFix

from app.flask_dropzone import Dropzone
from app.configuration import Config
from app.iris_engine.tasker.celery import make_celery
from app.iris_engine.tasker.celery import set_celery_flask_context
from app.iris_engine.access_control.oidc_handler import get_oidc_client
from app.jinja_filters import register_jinja_filters
from app.models.authorization import ac_flag_match_mask
from app.db import db


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

bc = Bcrypt()  # flask-bcrypt
ma = Marshmallow()
celery = make_celery(__name__)
app = Flask(__name__, static_folder='../static')


def ac_current_user_has_permission(*permissions):
    """
    Return True if current user has permission
    """
    if 'permissions' not in session:
        return False

    current_user_permissions = session['permissions']
    for permission in permissions:

        if ac_flag_match_mask(current_user_permissions, permission.value):
            return True

    return False


def ac_current_user_has_manage_perms():

    if session['permissions'] != 1 and session['permissions'] & 0x1FFFFF0 != 0:
        return True
    return False


register_jinja_filters(app.jinja_env)

app.jinja_env.globals.update(user_has_perm=ac_current_user_has_permission)
app.jinja_env.globals.update(user_has_manage_perms=ac_current_user_has_manage_perms)
app.jinja_options['autoescape'] = lambda _: True
app.jinja_env.autoescape = True

app.config.from_object(Config)
app.config['timezone'] = 'Europe/Paris'
from app.post_init import PostInit

cache = Cache(app)

db.init_app(app)

bc.init_app(app)

lm = LoginManager()  # flask-loginmanager
lm.init_app(app)  # init the login manager
ma.init_app(app)

dropzone = Dropzone(app)

set_celery_flask_context(celery, app)

#if app.config.get('DEVELOPMENT_ENABLED'):
CORS(app,
     supports_credentials=True,
     resources={r"/api/*": {"origins": [
         "https://127.0.0.1:5137",
         "https://localhost:5173",
         "https://localhost",
         "https://127.0.0.1",
         "http://app:8000",
         "http://frontend:5173",
     ]}})


app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
#app.wsgi_app = store.wsgi_middleware(app.wsgi_app)

socket_io = SocketIO(app, cors_allowed_origins="*")

alerts_namespace = AlertsNamespace('/alerts')
socket_io.on_namespace(alerts_namespace)

oidc_client = None
if app.config.get('AUTHENTICATION_TYPE') == 'oidc':
    oidc_client = get_oidc_client(app.config, app.logger)
from app.views import register_blueprints
from app.views import load_user
from app.views import load_user_from_request


@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.close()
    g.pop('auth_user', None)
    g.pop('auth_token_user_id', None)
    g.pop('auth_user_permissions', None)


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', app.config['IRIS_ALLOW_ORIGIN'])
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')

    return response


register_blueprints(app)

try:
    post_init = PostInit(app)
    post_init.run()

except Exception as e:
    app.logger.exception('Post init failed. IRIS not started')
    raise e

lm.user_loader(load_user)
lm.request_loader(load_user_from_request)

from app.blueprints.socket_io_event_handlers.case_event_handlers import register_case_event_handlers
from app.blueprints.socket_io_event_handlers.case_notes_event_handlers import register_notes_event_handlers
from app.blueprints.socket_io_event_handlers.update_event_handlers import register_update_event_handlers

register_case_event_handlers()
register_notes_event_handlers()
register_update_event_handlers()
