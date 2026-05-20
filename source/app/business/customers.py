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

from flask_sqlalchemy.pagination import Pagination

from app.datamgmt.db_operations import db_create
from app.models.customers import Client
from app.iris_engine.utils.tracker import track_activity
from app.datamgmt.manage.manage_users_db import add_user_to_customer
from app.datamgmt.client.client_db import get_paginated_customers
from app.datamgmt.client.client_db import get_customer
from app.datamgmt.client.client_db import get_customer_by_name
from app.datamgmt.client.client_db import update_customer
from app.datamgmt.client.client_db import delete_client
from app.models.errors import ObjectNotFoundError
from app.models.pagination_parameters import PaginationParameters


def customers_filter(user, pagination_parameters: PaginationParameters, is_server_administrator) -> Pagination:
    return get_paginated_customers(pagination_parameters, user.id, is_server_administrator)


# TODO maybe this method should be removed and always create a customer with at least a user
def customers_create(customer: Client):
    db_create(customer)


def customers_create_with_user(user, customer: Client):
    customers_create(customer)
    track_activity(f'Added customer {customer.name}', ctx_less=True)
    add_user_to_customer(user.id, customer.client_id)


def customers_get(identifier) -> Client:
    customer = get_customer(identifier)
    if not customer:
        raise ObjectNotFoundError()
    return customer


def customers_get_by_name(name) -> Client:
    customer = get_customer_by_name(name)
    if not customer:
        raise ObjectNotFoundError()
    return customer


def customers_exists_another_with_same_name(identifier, name: str) -> bool:
    customer = get_customer_by_name(name, case_insensitive=True)
    if not customer:
        return False
    if customer.client_id == identifier:
        return False
    return True


def customers_update():
    update_customer()


def customers_delete(customer: Client):
    delete_client(customer)
    track_activity(f'Deleted Customer with ID {customer.client_id}', ctx_less=True)
