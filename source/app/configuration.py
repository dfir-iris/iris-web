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

# --------- Configuration ---------
# read the private configuration file
import sys
from enum import Enum
import logging as log

import requests
import configparser
import os


# --------- Configuration ---------
# read the private configuration file
class IrisConfigException(Exception):
    pass


class IrisConfig(configparser.ConfigParser):
    """ From https://gist.github.com/jeffersfp/586c2570cd2bdb8385693a744aa13122 - @jeffersfp """

    def __init__(self, config_file):
        super(IrisConfig, self).__init__()

        self.read(config_file)
        self.validate_config()

    def validate_config(self):
        required_values = {
            'POSTGRES': {
            },
            'IRIS': {
            },
            'CELERY': {
            },
            'DEVELOPMENT': {
            }
        }

        for section, keys in required_values.items():
            if section not in self:
                raise IrisConfigException(
                    'Missing section %s in the configuration file' % section)


# --------- Configuration ---------
# read the private configuration file
config = configparser.ConfigParser()

if os.getenv("DOCKERIZED"):
    # The example config file has an invalid value so cfg will stay empty first
    config = IrisConfig(f'app{os.path.sep}config.docker.ini')
else:
    config = IrisConfig(f'app{os.path.sep}config.priv.ini')

# Fetch the values
PG_ACCOUNT_ = os.environ.get('DB_USER', config.get('POSTGRES', 'PG_ACCOUNT'))
PG_PASSWD_ = os.environ.get('DB_PASS', config.get('POSTGRES', 'PG_PASSWD'))
PGA_ACCOUNT_ = os.environ.get('POSTGRES_USER', config.get('POSTGRES', 'PGA_ACCOUNT'))
PGA_PASSWD_ = os.environ.get('POSTGRES_PASSWORD', config.get('POSTGRES', 'PGA_PASSWD'))
PG_SERVER_ = os.environ.get('DB_HOST', config.get('POSTGRES', 'PG_SERVER'))
PG_PORT_ = os.environ.get('DB_PORT', config.get('POSTGRES', 'PG_PORT'))
CELERY_BROKER_ = os.environ.get('CELERY_BROKER',
                                config.get('CELERY', 'BROKER',
                                           fallback=f"amqp://{config.get('CELERY', 'HOST', fallback='rabbitmq')}"))

if os.environ.get('IRIS_WORKER') is None:
    # Flask needs it for CSRF token and stuff
    SECRET_KEY_ = os.environ.get('SECRET_KEY', config.get('IRIS', 'SECRET_KEY'))
    SECURITY_PASSWORD_SALT_ = os.environ.get('SECURITY_PASSWORD_SALT', config.get('IRIS', 'SECURITY_PASSWORD_SALT'))

# Grabs the folder where the script runs.
basedir = os.path.abspath(os.path.dirname(__file__))

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


authentication_type = os.environ.get('IRIS_AUTHENTICATION_TYPE',
                                     config.get('AUTHENTICATION', 'AUTHENTICATION_TYPE', fallback="local"))

tls_root_ca = os.environ.get('TLS_ROOT_CA',
                             config.get('AUTHENTICATION', 'TLS_ROOT_CA', fallback=None))

app_public_url = os.environ.get('IRIS_PUBLIC_URL',
                                config.get("IRIS", "APP_PUBLIC_URL", fallback=None))

authentication_logout_url = None
authentication_account_service_url = None
authentication_token_introspection_url = None
authentication_client_id = None
authentication_client_secret = None
authentication_app_admin_role_name = None

if authentication_type == 'oidc_proxy':
    oidc_discovery_url = os.environ.get('OIDC_IRIS_DISCOVERY_URL',
                                        config.get('AUTHENTICATION', 'OIDC_IRIS_DISCOVERY_URL', fallback=""))

    try:
        oidc_discovery_response = requests.get(oidc_discovery_url, verify=tls_root_ca)

        if oidc_discovery_response.status_code == 200:
            response_json = oidc_discovery_response.json()

            authentication_logout_url = response_json.get('end_session_endpoint')
            authentication_account_service_url = f"{response_json.get('issuer')}/account"
            authentication_token_introspection_url = response_json.get('introspection_endpoint')
            authentication_jwks_url = response_json.get('jwks_uri')

        else:
            raise Exception("Unsuccessful authN server discovery")

        authentication_client_id = os.environ.get('OIDC_IRIS_CLIENT_ID',
                                                  config.get('AUTHENTICATION', 'OIDC_IRIS_CLIENT_ID', fallback=""))

        authentication_client_secret = os.environ.get('OIDC_IRIS_CLIENT_SECRET',
                                                      config.get('AUTHENTICATION', 'OIDC_IRIS_CLIENT_SECRET',
                                                                 fallback=""))

        authentication_app_admin_role_name = config.get('AUTHENTICATION', 'OIDC_IRIS_ADMIN_ROLE_NAME', fallback="")
    except Exception as e:
        log.error(f"OIDC ERROR - {e}")
        exit(0)
        pass
    else:
        log.info("OIDC configuration properly parsed")


# --------- CELERY ---------
class CeleryConfig():
    result_backend = "db+" + SQLALCHEMY_BASE_URI + "iris_tasks"  # use database as storage
    broker_url = CELERY_BROKER_
    result_extended = True
    result_serializer = "json"
    worker_pool_restarts = True


# --------- APP ---------
class Config():
    # Handled by bumpversion
    IRIS_VERSION = "v1.4.5"

    API_MIN_VERSION = "1.0.1"
    API_MAX_VERSION = "1.0.4"

    MODULES_INTERFACE_MIN_VERSION = '1.1'
    MODULES_INTERFACE_MAX_VERSION = '1.1'

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

    UPLOADED_PATH = config.get('IRIS', 'UPLOADED_PATH') if config.get('IRIS', 'UPLOADED_PATH',
                                                                      fallback=False) else "/home/iris/downloads"
    TEMPLATES_PATH = config.get('IRIS', 'TEMPLATES_PATH') if config.get('IRIS', 'TEMPLATES_PATH',
                                                                        fallback=False) else "/home/iris/user_templates"
    BACKUP_PATH = config.get('IRIS', 'BACKUP_PATH') if config.get('IRIS', 'BACKUP_PATH',
                                                                  fallback=False) else "/home/iris/server_data/backup"
    UPDATES_PATH = os.path.join(BACKUP_PATH, 'updates')

    RELEASE_URL = config.get('IRIS', 'RELEASE_URL') if config.get('IRIS', 'RELEASE_URL',
                                                                  fallback=False) else "https://api.github.com/repos/dfir-iris/iris-web/releases"

    RELEASE_SIGNATURE_KEY = config.get('IRIS', 'RELEASE_SIGNATURE_KEY') if config.get('IRIS', 'RELEASE_SIGNATURE_KEY',
                                                                                      fallback=False) else "dependencies/DFIR-IRIS_pkey.asc"

    PG_CLIENT_PATH = config.get('IRIS', 'PG_CLIENT_PATH') if config.get('IRIS', 'PG_CLIENT_PATH',
                                                                        fallback=False) else "/usr/bin"
    ASSET_STORE_PATH = config.get('IRIS', 'ASSET_STORE_PATH') if config.get('IRIS', 'ASSET_STORE_PATH',
                                                                            fallback=False) else "/home/iris/server_data/custom_assets"
    DATASTORE_PATH = config.get('IRIS', 'DATASTORE_PATH') if config.get('IRIS', 'DATASTORE_PATH',
                                                                        fallback=False) else "/home/iris/server_data/datastore"
    ASSET_SHOW_PATH = "/static/assets/img/graph"

    UPDATE_DIR_NAME = '_updates_'

    DROPZONE_MAX_FILE_SIZE = 1024 * 1024 * 1024 * 10  # 10 GB

    DROPZONE_TIMEOUT = 15 * 60 * 10000  # 15 Minutes of uploads per file

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

    if authentication_type == 'oidc_proxy':
        AUTHENTICATION_LOGOUT_URL = authentication_logout_url
        AUTHENTICATION_ACCOUNT_SERVICE_URL = authentication_account_service_url
        AUTHENTICATION_PROXY_LOGOUT_URL = f"/oauth2/sign_out?rd={AUTHENTICATION_LOGOUT_URL}?redirect_uri=/dashboard"
        AUTHENTICATION_TOKEN_INTROSPECTION_URL = authentication_token_introspection_url
        AUTHENTICATION_JWKS_URL = authentication_jwks_url
        AUTHENTICATION_CLIENT_ID = authentication_client_id
        AUTHENTICATION_CLIENT_SECRET = authentication_client_secret
        AUTHENTICATION_AUDIENCE = os.environ.get('OIDC_IRIS_AUDIENCE', config.get('AUTHENTICATION', 'OIDC_IRIS_AUDIENCE',
                                                                                  fallback=""))
        AUTHENTICATION_VERIFY_TOKEN_EXP = os.environ.get('OIDC_IRIS_VERIFY_TOKEN_EXPIRATION',
                                                         config.get('AUTHENTICATION', 'OIDC_IRIS_VERIFY_TOKEN_EXPIRATION',
                                                                    fallback=True))
        AUTHENTICATION_TOKEN_VERIFY_MODE = os.environ.get('OIDC_IRIS_TOKEN_VERIFY_MODE',
                                                          config.get('AUTHENTICATION', 'OIDC_IRIS_TOKEN_VERIFY_MODE',
                                                                     fallback='signature'))
        AUTHENTICATION_INIT_ADMINISTRATOR_EMAIL = os.environ.get('OIDC_IRIS_INIT_ADMINISTRATOR_EMAIL',
                                                                 config.get('AUTHENTICATION',
                                                                            'OIDC_IRIS_INIT_ADMINISTRATOR_EMAIL',
                                                                            fallback=""))
        AUTHENTICATION_APP_ADMIN_ROLE_NAME = authentication_app_admin_role_name

    """ Caching 
    """
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 300
