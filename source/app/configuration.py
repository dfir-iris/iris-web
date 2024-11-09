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
import ssl
# --------- Configuration ---------
# read the private configuration file
from datetime import timedelta
from enum import Enum
from pathlib import Path

import requests
# --------- Configuration ---------
# read the private configuration file
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


class IrisConfigException(Exception):
    pass


class IrisConfig(configparser.ConfigParser):
    """ From https://gist.github.com/jeffersfp/586c2570cd2bdb8385693a744aa13122 - @jeffersfp """

    def __init__(self):
        super(IrisConfig, self).__init__()

        # Azure Key Vault
        self.key_vault_name = self.load('AZURE', 'KEY_VAULT_NAME')
        if self.key_vault_name:
            self.az_credential = DefaultAzureCredential()
            self.az_client = SecretClient(vault_url=f"https://{self.key_vault_name}.vault.azure.net/",
                                          credential=self.az_credential)
            log.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(log.WARNING)

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

    def config_key_vault(self):
        """
        Load the settings to connect to Azure Key Vault
        """

    def load(self, section, option, fallback=None):
        """
        Load variable from different sources. Uses the following order
        1. Azure Key Vault
        2. Environment Variable
        3. Environment Variable deprecated
        3. Configuration File
        """

        loaders = [self._load_azure_key_vault,
                   self._load_env, self._load_env_deprecated,
                   self._load_file, self._load_file_deprecated]
        for loader in loaders:
            value = loader(section, option)
            if value:
                return value

        return fallback

    def _load_azure_key_vault(self, section, option):
        if not (hasattr(self, 'key_vault_name') and self.key_vault_name):
            return

        key = f"{section}-{option}".replace('_', '-')

        try:
            return self.az_client.get_secret(key).value
        except ResourceNotFoundError:
            return None

    def _load_env(self, section, option):
        return os.environ.get(f"{section}_{option}")

    def _load_env_deprecated(self, section, option):
        # Specify new_value : old_value
        mapping = {
            'POSTGRES_ADMIN_USER': 'DB_USER',
            'POSTGRES_ADMIN_PASSWORD': 'DB_PASS',
            'POSTGRES_SERVER': 'DB_HOST',
            'POSTGRES_PORT': 'DB_PORT',
            'IRIS_SECRET_KEY': 'SECRET_KEY',
            'IRIS_SECURITY_PASSWORD_SALT': 'SECURITY_PASSWORD_SALT',
            'IRIS_UPSTREAM_SERVER': 'APP_HOST',
            'IRIS_UPSTREAM_PORT': 'APP_PORT'
        }

        new_key = f"{section}_{option}"
        old_key = mapping.get(new_key)
        if not old_key:
            return

        value = os.environ.get(old_key)
        if value:
            log.warning(f"Environment variable {old_key} used which is deprecated. Please use {new_key}.")

        return value

    def _load_file(self, section, option):
        return self.get(section, option, fallback=None)

    def _load_file_deprecated(self, section, option):
        # Specify new_value : old_value
        mapping = {
            ('POSTGRES', 'USER'): ('POSTGRES', 'PG_ACCOUNT'),
            ('POSTGRES', 'PASSWORD'): ('POSTGRES', 'PG_PASSWD'),
            ('POSTGRES', 'ADMIN_USER'): ('POSTGRES', 'PGA_ACCOUNT'),
            ('POSTGRES', 'ADMIN_PASSWORD'): ('POSTGRES', 'PGA_PASSWD'),
            ('POSTGRES', 'SERVER'): ('POSTGRES', 'PG_SERVER'),
            ('POSTGRES', 'PORT'): ('POSTGRES', 'PG_PORT')
        }

        new_key = (section, option)
        old_key = mapping.get(new_key)
        if not old_key:
            return

        value = self.get(old_key[0], old_key[1], fallback=None)
        if value:
            log.warning(
                f"Configuration {old_key[0]}.{old_key[1]} found in configuration file. "
                f"This is a deprecated configuration. Please use {new_key[0]}.{new_key[1]}")

        return value


# --------- Configuration ---------
config = IrisConfig()

# Fetch the values
PG_ACCOUNT_ = config.load('POSTGRES', 'USER')
PG_PASSWD_ = config.load('POSTGRES', 'PASSWORD')
PGA_ACCOUNT_ = config.load('POSTGRES', 'ADMIN_USER')
PGA_PASSWD_ = config.load('POSTGRES', 'ADMIN_PASSWORD')
PG_SERVER_ = config.load('POSTGRES', 'SERVER')
PG_PORT_ = config.load('POSTGRES', 'PORT')
PG_DB_ = config.load('POSTGRES', 'DB', fallback='iris_db')
CELERY_BROKER_ = config.load('CELERY', 'BROKER',
                             fallback=f"amqp://{config.load('CELERY', 'HOST', fallback='rabbitmq')}")


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

SQLALCHEMY_BASE_ADMIN_URI = "postgresql+psycopg2://{user}:{passwd}@{server}:{port}/".format(user=PGA_ACCOUNT_,
                                                                                            passwd=PGA_PASSWD_,
                                                                                            server=PG_SERVER_,
                                                                                            port=PG_PORT_)


class AuthenticationType(Enum):
    local = 1
    oidc_proxy = 2


authentication_type = os.environ.get('IRIS_AUTHENTICATION_TYPE',
                                     config.get('IRIS', 'AUTHENTICATION_TYPE', fallback="local"))

authentication_create_user_if_not_exists = config.load('IRIS', 'AUTHENTICATION_CREATE_USER_IF_NOT_EXIST')

tls_root_ca = os.environ.get('TLS_ROOT_CA',
                             config.get('IRIS', 'TLS_ROOT_CA', fallback=None))

authentication_logout_url = None
authentication_account_service_url = None
authentication_token_introspection_url = None
authentication_client_id = None
authentication_client_secret = None
authentication_app_admin_role_name = None
authentication_jwks_url = None


if authentication_type == 'oidc_proxy':
    oidc_discovery_url = config.load('OIDC', 'IRIS_DISCOVERY_URL', fallback="")

    try:

        oidc_discovery_response = requests.get(oidc_discovery_url, verify=tls_root_ca)

        if oidc_discovery_response.status_code == 200:
            response_json = oidc_discovery_response.json()
            authentication_logout_url = response_json.get('end_session_endpoint')
            authentication_account_service_url = f"{response_json.get('issuer')}/account"
            authentication_token_introspection_url = response_json.get('introspection_endpoint')
            authentication_jwks_url = response_json.get('jwks_uri')

        else:
            raise IrisConfigException("Unsuccessful authN server discovery")

        authentication_client_id = config.load('OIDC', 'IRIS_CLIENT_ID', fallback="")

        authentication_client_secret = config.load('OIDC', 'IRIS_CLIENT_SECRET', fallback="")

        authentication_app_admin_role_name = config.load('OIDC', 'IRIS_ADMIN_ROLE_NAME', fallback="")

    except Exception as e:
        log.error(f"OIDC ERROR - {e}")
        exit(0)
        pass
    else:
        log.info("OIDC configuration properly parsed")


# --------- CELERY ---------
class CeleryConfig:
    result_backend = "db+" + SQLALCHEMY_BASE_URI + "iris_tasks"  # use database as storage
    broker_url = CELERY_BROKER_
    result_extended = True
    result_serializer = "json"
    worker_pool_restarts = True


# --------- APP ---------
class Config:
    # Handled by bumpversion
    IRIS_VERSION = "v2.4.15" # DO NOT EDIT THIS LINE MANUALLY

    if os.environ.get('IRIS_DEMO_VERSION') is not None and os.environ.get('IRIS_DEMO_VERSION') != 'None':
        IRIS_VERSION = os.environ.get('IRIS_DEMO_VERSION')

    API_MIN_VERSION = "2.0.4"
    API_MAX_VERSION = "2.0.5"

    MODULES_INTERFACE_MIN_VERSION = '1.1'
    MODULES_INTERFACE_MAX_VERSION = '1.2.0'

    if os.environ.get('IRIS_WORKER') is None:
        CSRF_ENABLED = True

        SECRET_KEY = config.load('IRIS', 'SECRET_KEY')

        SECURITY_PASSWORD_SALT = config.load('IRIS', 'SECURITY_PASSWORD_SALT')

        SECURITY_LOGIN_USER_TEMPLATE = 'login.html'

        IRIS_ADM_EMAIL = config.load('IRIS', 'ADM_EMAIL')
        IRIS_ADM_PASSWORD = config.load('IRIS', 'ADM_PASSWORD')
        IRIS_ADM_USERNAME = config.load('IRIS', 'ADM_USERNAME')
        IRIS_ADM_API_KEY = config.load('IRIS', 'ADM_API_KEY')

    PERMANENT_SESSION_LIFETIME = timedelta(minutes=config.load('IRIS', 'SESSION_TIMEOUT', fallback=1440))
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = True
    MFA_ENABLED = config.load('IRIS', 'MFA_ENABLED', fallback=False) == 'True'

    PG_ACCOUNT = PG_ACCOUNT_
    PG_PASSWD = PG_PASSWD_
    PGA_ACCOUNT = PGA_ACCOUNT_
    PGA_PASSWD = PGA_PASSWD_
    PG_SERVER = PG_SERVER_
    PG_PORT = PG_PORT_
    PG_DB = PG_DB_

    DB_RETRY_COUNT = config.load('DB', 'RETRY_COUNT', fallback=3)
    DB_RETRY_DELAY = config.load('DB', 'RETRY_DELAY', fallback=0.5)

    DEMO_MODE_ENABLED = config.load('IRIS_DEMO', 'ENABLED', fallback=False)
    if DEMO_MODE_ENABLED == 'True':
        DEMO_DOMAIN = config.load('IRIS_DEMO', 'DOMAIN', fallback=None)
        DEMO_USERS_SEED = config.load('IRIS_DEMO', 'USERS_SEED', fallback=0)
        DEMO_ADM_SEED = config.load('IRIS_DEMO', 'ADM_SEED', fallback=0)
        MAX_CONTENT_LENGTH = 200000

    WTF_CSRF_TIME_LIMIT = None

    """ SqlAlchemy configuration
    """
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_BASE_URI + PG_DB_
    SQLALCHEMY_BINDS = {
        'iris_tasks': SQLALCHEMY_BASE_URI + 'iris_tasks'
    }

    SQALCHEMY_PIGGER_URI = SQLALCHEMY_BASE_URI

    """ Dropzone configuration
    Set download path, max file upload size and timeout
    """
    APP_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    UPLOADED_PATH = config.load('IRIS', 'UPLOADED_PATH', fallback="/home/iris/downloads")
    TEMPLATES_PATH = config.load('IRIS', 'TEMPLATES_PATH', fallback="/home/iris/user_templates")
    BACKUP_PATH = config.load('IRIS', 'BACKUP_PATH', fallback="/home/iris/server_data/backup")
    UPDATES_PATH = os.path.join(BACKUP_PATH, 'updates')

    RELEASE_URL = config.load('IRIS', 'RELEASE_URL',
                              fallback="https://api.github.com/repos/dfir-iris/iris-web/releases")

    RELEASE_SIGNATURE_KEY = config.load('IRIS', 'RELEASE_SIGNATURE_KEY', fallback="dependencies/DFIR-IRIS_pkey.asc")

    PG_CLIENT_PATH = config.load('IRIS', 'PG_CLIENT_PATH', fallback="/usr/bin")
    ASSET_STORE_PATH = config.load('IRIS', 'ASSET_STORE_PATH', fallback="/home/iris/server_data/custom_assets")
    DATASTORE_PATH = config.load('IRIS', 'DATASTORE_PATH', fallback="/home/iris/server_data/datastore")
    ASSET_SHOW_PATH = "/static/assets/img/graph"

    ORGANISATION_NAME = config.load('IRIS', 'ORGANISATION_NAME', fallback='')
    LOGIN_BANNER_TEXT = config.load('IRIS', 'LOGIN_BANNER_TEXT', fallback='')
    LOGIN_PTFM_CONTACT = config.load('IRIS', 'LOGIN_PTFM_CONTACT', fallback='Please contact the platform administrator')

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
        DEVELOPMENT = config.load('DEVELOPMENT', 'IS_DEV_INSTANCE') == "True"

    """
        Authentication configuration
    """
    TLS_ROOT_CA = tls_root_ca

    AUTHENTICATION_TYPE = authentication_type
    AUTHENTICATION_CREATE_USER_IF_NOT_EXIST = (authentication_create_user_if_not_exists == "True")
    IRIS_NEW_USERS_DEFAULT_GROUP = config.load('IRIS', 'NEW_USERS_DEFAULT_GROUP', fallback='Analysts')
    AUTHENTICATION_LOCAL_FALLBACK = config.load('IRIS', 'AUTHENTICATION_LOCAL_FALLBACK', fallback="True") == "True"

    if authentication_type == 'oidc_proxy':
        AUTHENTICATION_LOGOUT_URL = authentication_logout_url
        AUTHENTICATION_ACCOUNT_SERVICE_URL = authentication_account_service_url
        AUTHENTICATION_PROXY_LOGOUT_URL = f"/oauth2/sign_out?rd={AUTHENTICATION_LOGOUT_URL}?redirect_uri=/dashboard"
        AUTHENTICATION_TOKEN_INTROSPECTION_URL = authentication_token_introspection_url
        AUTHENTICATION_JWKS_URL = authentication_jwks_url
        AUTHENTICATION_CLIENT_ID = authentication_client_id
        AUTHENTICATION_CLIENT_SECRET = authentication_client_secret
        AUTHENTICATION_AUDIENCE = config.load('OIDC', 'IRIS_AUDIENCE', fallback="")
        AUTHENTICATION_VERIFY_TOKEN_EXP = config.load('OIDC', 'IRIS_VERIFY_TOKEN_EXPIRATION',
                                                      fallback=True)
        AUTHENTICATION_TOKEN_VERIFY_MODE = config.load('OIDC', 'IRIS_TOKEN_VERIFY_MODE',
                                                       fallback='signature')
        AUTHENTICATION_INIT_ADMINISTRATOR_EMAIL = config.load('OIDC', 'IRIS_INIT_ADMINISTRATOR_EMAIL',
                                                              fallback="")
        AUTHENTICATION_APP_ADMIN_ROLE_NAME = authentication_app_admin_role_name

    elif authentication_type == 'ldap':
        LDAP_SERVER = config.load('LDAP', 'SERVER')
        if LDAP_SERVER is None:
            raise Exception('LDAP enabled and no server configured')

        LDAP_PORT = config.load('LDAP', 'PORT')
        if LDAP_PORT is None:
            raise Exception('LDAP enabled and no server configured')

        LDAP_USER_PREFIX = config.load('LDAP', 'USER_PREFIX', '')
        if LDAP_USER_PREFIX is None:
            raise Exception('LDAP enabled and no user prefix configured')

        LDAP_USER_SUFFIX = config.load('LDAP', 'USER_SUFFIX', '')
        if LDAP_USER_SUFFIX is None:
            raise Exception('LDAP enabled and no user suffix configured')

        LDAP_AUTHENTICATION_TYPE = config.load('LDAP', 'AUTHENTICATION_TYPE')

        LDAP_SEARCH_DN = config.load('LDAP', 'SEARCH_DN')
        if authentication_create_user_if_not_exists and LDAP_SEARCH_DN is None:
            raise Exception('LDAP enabled with user provisioning: LDAP_SEARCH_DN should be set')
        LDAP_ATTRIBUTE_IDENTIFIER = config.load('LDAP', 'ATTRIBUTE_IDENTIFIER')
        if authentication_create_user_if_not_exists and LDAP_ATTRIBUTE_IDENTIFIER is None:
            raise Exception('LDAP enabled with user provisioning: LDAP_ATTRIBUTE_IDENTIFIER should be set')

        LDAP_ATTRIBUTE_DISPLAY_NAME = config.load('LDAP', 'ATTRIBUTE_DISPLAY_NAME')
        LDAP_ATTRIBUTE_MAIL = config.load('LDAP', 'ATTRIBUTE_MAIL')

        LDAP_USE_SSL = config.load('LDAP', 'USE_SSL', fallback='True')
        LDAP_USE_SSL = (LDAP_USE_SSL == 'True')

        LDAP_VALIDATE_CERTIFICATE = config.load('LDAP', 'VALIDATE_CERTIFICATE', fallback='True')
        LDAP_VALIDATE_CERTIFICATE = (LDAP_VALIDATE_CERTIFICATE == 'True')

        ldap_tls_v = config.load('LDAP', 'TLS_VERSION', '1.2')
        if ldap_tls_v not in ['1.0', '1.1', '1.2']:
            raise Exception(f'Unsupported LDAP TLS version {ldap_tls_v}')

        if ldap_tls_v == '1.1':
            LDAP_TLS_VERSION = ssl.PROTOCOL_TLSv1_1
        elif ldap_tls_v == '1.2':
            LDAP_TLS_VERSION = ssl.PROTOCOL_TLSv1_2
        elif ldap_tls_v == '1.0':
            LDAP_TLS_VERSION = ssl.PROTOCOL_TLSv1

        proto = 'ldaps' if LDAP_USE_SSL else 'ldap'
        LDAP_CONNECT_STRING = f'{proto}://{LDAP_SERVER}:{LDAP_PORT}'

        if LDAP_USE_SSL:
            LDAP_SERVER_CERTIFICATE = config.load('LDAP', 'SERVER_CERTIFICATE')
            if not Path(f'certificates/ldap/{LDAP_SERVER_CERTIFICATE}').is_file():
                log.error(f'Unable to read LDAP certificate file certificates/ldap/{LDAP_SERVER_CERTIFICATE}')
                raise Exception(f'Unable to read LDAP certificate file certificates/ldap/{LDAP_SERVER_CERTIFICATE}')

            LDAP_PRIVATE_KEY = config.load('LDAP', 'PRIVATE_KEY')
            if LDAP_PRIVATE_KEY and not Path(f'certificates/ldap/{LDAP_PRIVATE_KEY}').is_file():
                log.error(f'Unable to read LDAP certificate file certificates/ldap/{LDAP_PRIVATE_KEY}')
                raise Exception(f'Unable to read LDAP certificate file certificates/ldap/{LDAP_PRIVATE_KEY}')

            PRIVATE_KEY_PASSWORD = config.load('LDAP', 'PRIVATE_KEY_PASSWORD', fallback=None)

            LDAP_CA_CERTIFICATE = config.load('LDAP', 'CA_CERTIFICATE')
            if LDAP_CA_CERTIFICATE and not Path(f'certificates/ldap/{LDAP_CA_CERTIFICATE}').is_file():
                log.error(f'Unable to read LDAP certificate file certificates/ldap/{LDAP_CA_CERTIFICATE}')
                raise Exception(f'Unable to read LDAP certificate file certificates/ldap/{LDAP_CA_CERTIFICATE}')

            LDAP_CUSTOM_TLS_CONFIG = config.load('LDAP', 'CUSTOM_TLS_CONFIG', fallback='True')
            LDAP_CUSTOM_TLS_CONFIG = (LDAP_CUSTOM_TLS_CONFIG == 'True')

    elif authentication_type == 'oidc':
        OIDC_ISSUER_URL = config.load('OIDC', 'ISSUER_URL')
        OIDC_CLIENT_ID = config.load('OIDC', 'CLIENT_ID')
        OIDC_CLIENT_SECRET = config.load('OIDC', 'CLIENT_SECRET')
        OIDC_AUTH_ENDPOINT = config.load('OIDC', 'AUTH_ENDPOINT', fallback=None)
        OIDC_TOKEN_ENDPOINT = config.load('OIDC', 'TOKEN_ENDPOINT', fallback=None)
        OIDC_END_SESSION_ENDPOINT = config.load('OIDC', 'END_SESSION_ENDPOINT', fallback=None)
        OIDC_SCOPES = config.load('OIDC', 'SCOPES', fallback="openid email profile")
        OIDC_MAPPING_USERNAME = config.load('OIDC', 'MAPPING_USERNAME', fallback='preferred_username')
        OIDC_MAPPING_EMAIL = config.load('OIDC', 'MAPPING_EMAIL', fallback='email')

    """ Caching 
    """
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 300

    log.info(f'IRIS Server {IRIS_VERSION}')
    log.info(f'Min. API version supported: {API_MIN_VERSION}')
    log.info(f'Max. API version supported: {API_MAX_VERSION}')
    log.info(f'Min. module interface version supported: {MODULES_INTERFACE_MIN_VERSION}')
    log.info(f'Max. module interface version supported: {MODULES_INTERFACE_MAX_VERSION}')
    log.info(f'Session lifetime: {PERMANENT_SESSION_LIFETIME}')
    log.info(f'Authentication mechanism configured: {AUTHENTICATION_TYPE}')
    log.info(f'Authentication local fallback {"enabled" if AUTHENTICATION_LOCAL_FALLBACK else "disabled"}')
    log.info(f'MFA {"enabled" if MFA_ENABLED else "disabled"}')
    log.info(f'Create user during authentication: {"enabled" if AUTHENTICATION_CREATE_USER_IF_NOT_EXIST else "disabled"}')
