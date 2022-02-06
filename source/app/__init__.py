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
import logging
from flask import Flask
from flask.logging import default_handler
from flask_marshmallow import Marshmallow
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
import urllib.parse

from werkzeug.middleware.proxy_fix import ProxyFix

from app.flask_dropzone import Dropzone
from app.iris_engine.tasker.celery import make_celery
from flask_logging import Filter

from sqlalchemy_imageattach.stores.fs import HttpExposedFileSystemStore

import os
import logging as logger


class ReverseProxied(object):
    def __init__(self, flask_app):
        self._app = flask_app

    def __call__(self, environ, start_response):
        scheme = environ.get('HTTP_X_FORWARDED_PROTO', None)
        if scheme is not None:
            environ['wsgi.url_scheme'] = scheme
        return self._app(environ, start_response)


APP_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(APP_PATH, 'templates/')

# Grabs the folder where the script runs.
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

LOG_FORMAT = '%(asctime)s :: %(levelname)s :: %(module)s :: %(funcName)s :: %(message)s'
LOG_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

logger.basicConfig(level=logger.INFO, format=LOG_FORMAT, datefmt=LOG_TIME_FORMAT)

app.jinja_env.filters['unquote'] = lambda u: urllib.parse.unquote(u)
app.config.from_object('app.configuration.Config')

db = SQLAlchemy(app)  # flask-sqlalchemy

bc = Bcrypt(app)  # flask-bcrypt

lm = LoginManager()  # flask-loginmanager
lm.init_app(app)  # init the login manager

ma = Marshmallow(app) # Init marshmallow

dropzone = Dropzone(app)

celery = make_celery(app)

filter = Filter('static')

store = HttpExposedFileSystemStore(
    path='images',
    prefix='/static/assets/images/'
)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.wsgi_app = store.wsgi_middleware(app.wsgi_app)

socket_io = SocketIO(app, cors_allowed_origins="*")


@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

from app import views


