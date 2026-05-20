#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
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
from flask import Response
from flask import Blueprint

from app import app
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_error


class ServerOperations:
    def __init__(self):
        pass

    @staticmethod
    def get_authentication_settings():
        try:
            auth_requirements = {
                "oidc_enabled": app.config.get("AUTHENTICATION_TYPE") == "oidc",
                "mfa_enabled": app.config.get("MFA_ENABLED"),
            }
            return response_api_success(auth_requirements)
        except Exception as e:
            return response_api_error("Data error", data=str(e))


server_blueprint = Blueprint("server_rest_v2", __name__, url_prefix="/server")

server_operations = ServerOperations()


@server_blueprint.get("/authentication-settings")
def server_get_authsettings() -> Response:
    return server_operations.get_authentication_settings()
