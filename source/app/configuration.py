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

import os
import logging as log
import configparser

# --------- Configuration ---------
# read the private configuration file
config = configparser.ConfigParser()

if os.getenv("DOCKERIZED"):
    config.read('app/config.docker.ini')
else:
    config.read('app/config.priv.ini')

# Fetch the values
misp_url = config.get('MISP', 'MISP_URL')
misp_key = config.get('MISP', 'MISP_KEY')
misp_verifycert = config.get('MISP', 'MISP_VERIFYCERT') != "False"
misp_http_proxy = config.get('MISP', 'MISP_PROXY_HTTP')
misp_https_proxy = config.get('MISP', 'MISP_PROXY_HTTPS')

PG_ACCOUNT_ = os.environ.get('DB_USER', config.get('POSTGRES', 'PG_ACCOUNT'))
PG_PASSWD_ = os.environ.get('DB_PASS', config.get('POSTGRES', 'PG_ACCOUNT'))
PGA_ACCOUNT_ = os.environ.get('POSTGRES_USER', config.get('POSTGRES', 'PGA_ACCOUNT'))
PGA_PASSWD_ = os.environ.get('POSTGRES_PASSWORD', config.get('POSTGRES', 'PGA_PASSWD'))
PG_SERVER_ = os.environ.get('DB_HOST', config.get('POSTGRES', 'PG_SERVER'))
PG_PORT_ = os.environ.get('DB_PORT', config.get('POSTGRES', 'PG_PORT'))

if os.environ.get('IRIS_WORKER') is None:
    # Flask needs it for CSRF token and stuff
    SECRET_KEY_ = os.environ.get('SECRET_KEY', config.get('IRIS', 'SECRET_KEY'))
    SECURITY_PASSWORD_SALT_ = os.environ.get('SECURITY_PASSWORD_SALT', config.get('IRIS', 'SECURITY_PASSWORD_SALT'))


# Grabs the folder where the script runs.
basedir = os.path.abspath(os.path.dirname(__file__))

# --------- LOGGING ---------
LOG_FORMAT = '%(asctime)s :: %(levelname)s :: %(module)s :: %(funcName)s :: %(message)s'
LOG_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
log.basicConfig(level=log.INFO, format=LOG_FORMAT, datefmt=LOG_TIME_FORMAT)


# Build of SQLAlchemy connectors. One is admin and the other is only for iris. Admin is needed to create new DB
SQLALCHEMY_BASE_URI = "postgresql+psycopg2://{user}:{passwd}@{server}:{port}/".format(user=PG_ACCOUNT_,
                                                                                      passwd=PG_PASSWD_,
                                                                                      server=PG_SERVER_,
                                                                                      port=PG_PORT_)

SQLALCHEMY_BASEA_URI = "postgresql+psycopg2://{user}:{passwd}@{server}:{port}/".format(user=PGA_ACCOUNT_,
                                                                                       passwd=PGA_PASSWD_,
                                                                                       server=PG_SERVER_,
                                                                                       port=PG_PORT_)


# --------- CELERY ---------
class CeleryConfig():
    result_backend = "db+" + SQLALCHEMY_BASE_URI + "iris_tasks"  # use database as storage
    broker_url = "amqp://localhost" if not os.getenv('DOCKERIZED') else "amqp://rabbitmq"
    result_extended = True
    result_serializer = "json"
    task_routes = ([
        ('app.iris_engine.tasker.tasks.task_kbh_import', { 'route' : 'case_import'}),
        ('app.iris_engine.tasker.tasks.task_feed_iris', { 'route' : 'case_import'})
    ],)


# --------- APP ---------
class Config():

    # Handled by bumpversion
    IRIS_VERSION = "v1.2.0"

    if os.environ.get('IRIS_WORKER') is None:
        CSRF_ENABLED = True

        SECRET_KEY = SECRET_KEY_

        SECURITY_PASSWORD_SALT = SECURITY_PASSWORD_SALT_

        SECURITY_LOGIN_USER_TEMPLATE = 'login.html'

    PG_ACCOUNT = PG_ACCOUNT_
    PG_PASSWD = PG_PASSWD_
    PGA_ACCOUNT = PGA_ACCOUNT_
    PGA_PASSWD = PGA_PASSWD_
    PG_SERVER = PG_SERVER_
    PG_PORT = PG_PORT_

    """ SqlAlchemy configuration
    """
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_BASE_URI + 'iris_db'
    SQLALCHEMY_BINDS = {
        'iris_tasks': SQLALCHEMY_BASE_URI + 'iris_tasks'
    }

    SQALCHEMY_PIGGER_URI = SQLALCHEMY_BASE_URI

    """ Dropzone configuration
    Set download path, max file upload size and timeout
    """
    APP_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    UPLOADED_PATH = config.get('IRIS', 'UPLOADED_PATH') if config.get('IRIS', 'UPLOADED_PATH', fallback=False) else "/home/iris/downloads"
    TEMPLATES_PATH = config.get('IRIS', 'TEMPLATES_PATH') if config.get('IRIS', 'TEMPLATES_PATH', fallback=False) else "/home/iris/user_templates"

    UPDATE_DIR_NAME = '_updates_'

    DROPZONE_MAX_FILE_SIZE = 1024

    MAX_CONTENT_LENGTH = 1024 * 1024 * 1024

    DROPZONE_TIMEOUT = 5 * 60 * 10000  # 5 Minutes of uploads per file

    """ Celery configuration
    Configure URL and backend
    """
    CELERY = CeleryConfig

    if os.getenv('IRIS_DEV'):
        DEVELOPMENT = True
    else:
        DEVELOPMENT = config.get('DEVELOPMENT', 'IS_DEV_INSTANCE') == "True"
