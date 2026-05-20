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

from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_current_user_has_permission
from app.models.authorization import Permissions
from app.schema.marshables import CustomerSchema
from app.models.errors import ObjectNotFoundError
from app.models.errors import ElementInUseError
from app.business.customers import customers_create_with_user
from app.business.customers import customers_filter
from app.business.customers import customers_get
from app.business.customers import customers_update
from app.business.customers import customers_delete
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.parsing import parse_pagination_parameters


class CustomersOperations:

    def __init__(self):
        self._schema = CustomerSchema()

    def search(self):
        pagination_parameters = parse_pagination_parameters(request)
        user_is_server_administrator = ac_current_user_has_permission(Permissions.server_administrator)
        customers = customers_filter(iris_current_user, pagination_parameters, user_is_server_administrator)
        return response_api_paginated(self._schema, customers)

    def create(self):
        try:
            request_data = request.get_json()
            customer = self._schema.load(request_data)
            customers_create_with_user(iris_current_user, customer)
            result = self._schema.dump(customer)
            return response_api_created(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)

    def read(self, identifier):
        try:
            customer = customers_get(identifier)
            result = self._schema.dump(customer)
            return response_api_success(result)
        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, identifier):
        try:
            customer = customers_get(identifier)
            request_data = request.get_json()
            request_data['customer_id'] = identifier
            updated_customer = self._schema.load(request_data, instance=customer)
            customers_update()
            result = self._schema.dump(updated_customer)
            return response_api_success(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)
        except ObjectNotFoundError:
            return response_api_not_found()

    @staticmethod
    def delete(identifier):
        try:
            customer = customers_get(identifier)
            customers_delete(customer)
            return response_api_deleted()

        except ObjectNotFoundError:
            return response_api_not_found()
        except ElementInUseError as e:
            return response_api_error(e.get_message())


customers_blueprint = Blueprint('customers_rest_v2', __name__, url_prefix='/customers')

customers_operations = CustomersOperations()


@customers_blueprint.get('')
@ac_api_requires(Permissions.customers_read)
def search_customers():
    return customers_operations.search()


@customers_blueprint.post('')
@ac_api_requires(Permissions.customers_write)
def create_customer():
    return customers_operations.create()


@customers_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.customers_read)
def get_customer(identifier):
    return customers_operations.read(identifier)


@customers_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.customers_write)
def put_customer(identifier):
    return customers_operations.update(identifier)


@customers_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.customers_write)
def delete_user(identifier):
    return customers_operations.delete(identifier)
