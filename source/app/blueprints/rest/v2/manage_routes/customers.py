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
from app.schema.marshables import ContactSchema
from app.schema.marshables import CustomerSchema
from app.models.errors import ObjectNotFoundError
from app.models.errors import ElementInUseError
from app.models.errors import BusinessProcessingError
from app.business.customers import customers_create_with_user
from app.business.customers import customers_filter
from app.business.customers import customers_get
from app.business.customers import customers_update
from app.business.customers import customers_delete
from app.business.customers_contacts import customers_contacts_create
from app.business.customers_contacts import customers_contacts_delete
from app.business.customers_contacts import customers_contacts_get
from app.business.customers_contacts import customers_contacts_list
from app.business.customers_contacts import customers_contacts_update
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
            # Embed contacts so the UI can render the detail panel
            # without a second round-trip. Matches the legacy GET
            # /manage/customers/<id> behaviour the SvelteKit client
            # already types for (`Customer.contacts?: ...`).
            result['contacts'] = ContactSchema().dump(
                customers_contacts_list(identifier), many=True
            )
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


class CustomersContactsOperations:
    """REST surface for `/customers/<id>/contacts[/<contact_id>]`.

    Mirrors `CustomersOperations` shape (search / create / read /
    update / delete) so the routing layer below stays uniform. Every
    handler verifies that the contact (when one is named) actually
    belongs to the parent customer — a contact_id from another
    customer would otherwise authorise edits via a sibling URL.
    """

    def __init__(self):
        self._schema = ContactSchema()

    @staticmethod
    def _ensure_parent(client_id):
        customers_get(client_id)

    def _ensure_owns(self, client_id, contact_id):
        contact = customers_contacts_get(contact_id)
        if contact.client_id != client_id:
            raise ObjectNotFoundError()
        return contact

    def list(self, client_id):
        try:
            self._ensure_parent(client_id)
            return response_api_success(
                self._schema.dump(customers_contacts_list(client_id), many=True)
            )
        except ObjectNotFoundError:
            return response_api_not_found()

    def create(self, client_id):
        try:
            self._ensure_parent(client_id)
            request_data = request.get_json() or {}
            # Force the parent id from the URL — the schema requires
            # client_id, and trusting the body would let a client write
            # contacts under a different customer.
            request_data['client_id'] = client_id
            contact = self._schema.load(request_data)
            customers_contacts_create(contact)
            return response_api_created(self._schema.dump(contact))
        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)
        except ObjectNotFoundError:
            return response_api_not_found()

    def read(self, client_id, contact_id):
        try:
            contact = self._ensure_owns(client_id, contact_id)
            return response_api_success(self._schema.dump(contact))
        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, client_id, contact_id):
        try:
            contact = self._ensure_owns(client_id, contact_id)
            request_data = request.get_json() or {}
            request_data['client_id'] = client_id
            self._schema.load(request_data, instance=contact, partial=True)
            customers_contacts_update(contact)
            return response_api_success(self._schema.dump(contact))
        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)
        except ObjectNotFoundError:
            return response_api_not_found()

    def delete(self, client_id, contact_id):
        try:
            contact = self._ensure_owns(client_id, contact_id)
            customers_contacts_delete(contact)
            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()
        except (ElementInUseError, BusinessProcessingError) as e:
            return response_api_error(e.get_message())


customers_blueprint = Blueprint('customers_rest_v2', __name__, url_prefix='/customers')

customers_operations = CustomersOperations()
customers_contacts_operations = CustomersContactsOperations()


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


@customers_blueprint.get('/<int:identifier>/contacts')
@ac_api_requires(Permissions.customers_read)
def list_customer_contacts(identifier):
    return customers_contacts_operations.list(identifier)


@customers_blueprint.post('/<int:identifier>/contacts')
@ac_api_requires(Permissions.customers_write)
def create_customer_contact(identifier):
    return customers_contacts_operations.create(identifier)


@customers_blueprint.get('/<int:identifier>/contacts/<int:contact_id>')
@ac_api_requires(Permissions.customers_read)
def get_customer_contact(identifier, contact_id):
    return customers_contacts_operations.read(identifier, contact_id)


@customers_blueprint.put('/<int:identifier>/contacts/<int:contact_id>')
@ac_api_requires(Permissions.customers_write)
def put_customer_contact(identifier, contact_id):
    return customers_contacts_operations.update(identifier, contact_id)


@customers_blueprint.delete('/<int:identifier>/contacts/<int:contact_id>')
@ac_api_requires(Permissions.customers_write)
def delete_customer_contact(identifier, contact_id):
    return customers_contacts_operations.delete(identifier, contact_id)
