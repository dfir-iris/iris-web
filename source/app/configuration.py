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
import os

# --------- Configuration ---------
# read the private configuration file

config = configparser.ConfigParser()

if os.getenv("DOCKERIZED"):
    config.read(f'app{os.path.sep}config.docker.ini')
else:
    config.read(f'app{os.path.sep}config.priv.ini')

# Fetch the values
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
    worker_pool_restarts = True


# --------- APP ---------
class Config():

    # Handled by bumpversion
    IRIS_VERSION = "v1.4.4"

    API_MIN_VERSION = "1.0.1"
    API_MAX_VERSION = "1.0.3"

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
    ASSET_SHOW_PATH = "/static/assets/img/graph"

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

    """ Caching 
    """
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 300
