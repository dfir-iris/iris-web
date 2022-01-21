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

import configparser
import logging as log
import os
# --------- Configuration ---------
# read the private configuration file
import sys
from enum import Enum

import requests

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
PG_PASSWD_ = os.environ.get('DB_PASS', config.get('POSTGRES', 'PG_PASSWD'))
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
SQLALCHEMY_BASE_URI = "postgresql+psycopg2://{user}:{passwd}@{server}:{port}/".format(
    user=PG_ACCOUNT_,
    passwd=PG_PASSWD_,
    server=PG_SERVER_,
    port=PG_PORT_
)

SQLALCHEMY_BASEA_URI = "postgresql+psycopg2://{user}:{passwd}@{server}:{port}/".format(
    user=PGA_ACCOUNT_,
    passwd=PGA_PASSWD_,
    server=PG_SERVER_,
    port=PG_PORT_
)


class AuthenticationType(Enum):
    local = 1
    oidc_proxy = 2


authentication_type = getattr(
    getattr(AuthenticationType, config.get('AUTHENTICATION', 'AUTHENTICATION_TYPE', fallback=""), None), 'name',
    'local')

tls_root_ca = config.get('AUTHENTICATION', 'TLS_ROOT_CA', fallback=None)

app_public_url = config.get("IRIS", "APP_PUBLIC_URL", fallback=None)

# TODO: cette variable pourra être instanciée avec l'url pour le logout local
authentication_logout_url = None
authentication_account_service_url = None
authentication_token_introspection_url = None
authentication_client_id = None
authentication_client_secret = None
authentication_app_admin_role_name = None

if authentication_type == 'oidc_proxy':
    oidc_discovery_url = config.get('AUTHENTICATION', 'OIDC_DISCOVERY_URL', fallback="")
    try:
        oidc_discovery_response = requests.get(oidc_discovery_url, verify=tls_root_ca)

        if oidc_discovery_response.status_code == 200:
            response_json = oidc_discovery_response.json()

            authentication_logout_url = response_json.get('end_session_endpoint')
            authentication_account_service_url = f"{response_json.get('issuer')}/account"
            authentication_token_introspection_url = response_json.get('introspection_endpoint')
        else:
            raise Exception("Unsuccessful authN server discovery")

        authentication_client_id = config.get('AUTHENTICATION', 'OIDC_IRIS_CLIENT_ID')
        authentication_client_secret = config.get('AUTHENTICATION', 'OIDC_IRIS_CLIENT_SECRET')
        authentication_app_admin_role_name = config.get('AUTHENTICATION', 'OIDC_IRIS_ADMIN_ROLE_NAME')
    except Exception as e:
        log.error(f"OIDC ERROR - {e}")
        exit(0)
        pass
    else:
        log.info("OIDC configuration properly parsed")


# --------- CELERY ---------
class CeleryConfig():
    result_backend = "db+" + SQLALCHEMY_BASE_URI + "iris_tasks"  # use database as storage
    broker_url = "amqp://localhost" if not os.getenv('DOCKERIZED') else "amqp://rabbitmq"
    result_extended = True
    result_serializer = "json"
    task_routes = (
        [
            ('app.iris_engine.tasker.tasks.task_kbh_import', {'route': 'case_import'}),
            ('app.iris_engine.tasker.tasks.task_feed_iris', {'route': 'case_import'})
        ],
    )


# --------- APP ---------
class Config():
    # Handled by bumpversion
    IRIS_VERSION = "v1.2.1"

    API_MIN_VERSION = "1.0.0"
    API_MAX_VERSION = "1.0.0"

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

    """
        Authentication configuration
    """
    TLS_ROOT_CA = tls_root_ca

    APP_PUBLIC_URL = app_public_url

    AUTHENTICATION_TYPE = authentication_type
    AUTHENTICATION_LOGOUT_URL = authentication_logout_url
    AUTHENTICATION_ACCOUNT_SERVICE_URL = authentication_account_service_url
    AUTHENTICATION_PROXY_LOGOUT_URL = f"/oauth2/sign_out?rd={AUTHENTICATION_LOGOUT_URL}?redirect_uri={APP_PUBLIC_URL}"
    AUTHENTICATION_TOKEN_INTROSPECTION_URL = authentication_token_introspection_url
    AUTHENTICATION_CLIENT_ID = authentication_client_id
    AUTHENTICATION_CLIENT_SECRET = authentication_client_secret

    AUTHENTICATION_APP_ADMIN_ROLE_NAME = authentication_app_admin_role_name
