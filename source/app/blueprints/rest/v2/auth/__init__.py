#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

from flask import Blueprint
from flask_login import current_user

from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.schema.marshables import UserSchema


auth_blueprint = Blueprint('auth', __name__, url_prefix='/auth')


# TODO shouldn't we rather have /api/v2/users/{identifier}?
#@auth_blueprint.route('/whoami', methods=['GET'])
def whoami():
    """
    Returns information about the currently authenticated user.
    """

    # Ensure we are authenticated
    if not current_user.is_authenticated:
        return response_api_error("Unauthenticated")

    # Return the current_user dict
    return response_api_success(data=UserSchema(only=[
        'id', 'user_name', 'user_login', 'user_email'
    ]).dump(current_user))
