#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
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
from flask import request
from marshmallow import ValidationError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_deleted
from app.schema.marshables import UserSchemaForAPIV2
from app.models.authorization import Permissions
from app.models.errors import ObjectNotFoundError
from app.models.errors import BusinessProcessingError
from app.business.users import users_create
from app.business.users import users_get
from app.business.users import users_update
from app.business.users import users_delete


class Users:

    def __init__(self):
        self._schema = UserSchemaForAPIV2()

    def create(self):
        try:
            request_data = request.get_json()
            request_data['user_id'] = 0
            request_data['user_active'] = request_data.get('user_active', True)
            user = self._schema.load(request_data)
            user = users_create(user, request_data['user_active'])
            result = self._schema.dump(user)
            return response_api_created(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)

    def read(self, identifier):
        try:
            user = users_get(identifier)
            result = self._schema.dump(user)
            return response_api_success(result)
        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, identifier):

        try:
            user = users_get(identifier)
            request_data = request.get_json()
            request_data['user_id'] = identifier
            new_user = self._schema.load(request_data, instance=user, partial=True)
            user_updated = users_update(new_user, request_data.get('user_password'))
            result = self._schema.dump(user_updated)
            return response_api_success(result)

        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)

        except ObjectNotFoundError:
            return response_api_not_found()

    def delete(self, identifier):
        try:
            user = users_get(identifier)
            users_delete(user)
            return response_api_deleted()

        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())


users = Users()
users_blueprint = Blueprint('users_rest_v2', __name__, url_prefix='/users')


@users_blueprint.post('')
@ac_api_requires(Permissions.server_administrator)
def create_user():
    return users.create()


@users_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def get_user(identifier):
    return users.read(identifier)


@users_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def put_user(identifier):
    return users.update(identifier)


@users_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def delete_user(identifier):
    return users.delete(identifier)
