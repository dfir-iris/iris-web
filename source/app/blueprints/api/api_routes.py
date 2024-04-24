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

from flask import Blueprint

from app import app
from app.util import ac_api_requires
from app.util import response_success

api_blueprint = Blueprint(
    'api',
    __name__,
    template_folder='templates'
)


# CONTENT ------------------------------------------------
@api_blueprint.route('/api/ping', methods=['GET'])
@ac_api_requires()
def api_ping():
    return response_success("pong")


@api_blueprint.route('/api/versions', methods=['GET'])
@ac_api_requires()
def api_version():
    versions = {
        "iris_current": app.config.get('IRIS_VERSION'),
        "api_min": app.config.get('API_MIN_VERSION'),
        "api_current": app.config.get('API_MAX_VERSION')
    }

    return response_success(data=versions)
