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

from sqlalchemy import func
from sqlalchemy import and_
from typing import List
from typing import Optional
from flask_sqlalchemy.pagination import Pagination

from app.datamgmt.db_operations import db_delete
from app.db import db
from app.models.errors import ElementInUseError
from app.models.cases import Cases
from app.models.customers import Client
from app.models.models import Contact
from app.models.authorization import User
from app.models.authorization import UserClient
from app.models.pagination_parameters import PaginationParameters
from app.datamgmt.filtering import paginate


# TODO most probably rename into update (or save?) and make more generic, maybe just use the preceding method?
def update_contact():
    db.session.commit()


# TODO same
def update_customer():
    db.session.commit()


def get_client_list(current_user_id: int, is_server_administrator: bool) -> List[dict]:
    if not is_server_administrator:
        filter = and_(
            Client.client_id == UserClient.client_id,
            UserClient.user_id == current_user_id
        )
    else:
        filter = and_()

    client_list = Client.query.with_entities(
        Client.name.label('customer_name'),
        Client.client_id.label('customer_id'),
        Client.client_uuid.label('customer_uuid'),
        Client.description.label('customer_description'),
        Client.sla.label('customer_sla'),
        Client.custom_attributes
    ).filter(
        filter
    ).all()

    output = [c._asdict() for c in client_list]

    return output


def get_paginated_customers(pagination_parameters: PaginationParameters, current_user_identifier: int, is_server_administrator: bool) -> Pagination:
    query = Client.query

    if not is_server_administrator:
        query = query.filter(
            Client.client_id == UserClient.client_id,
            UserClient.user_id == current_user_identifier
        )

    return paginate(Client, pagination_parameters, query)


def get_customer(client_id: int) -> Optional[Client]:
    return Client.query.filter(Client.client_id == client_id).first()


def get_client_api(client_id: str) -> Client:
    client = Client.query.with_entities(
        Client.name.label('customer_name'),
        Client.client_id.label('customer_id'),
        Client.client_uuid.label('customer_uuid'),
        Client.description.label('customer_description'),
        Client.sla.label('customer_sla'),
        Client.custom_attributes
    ).filter(Client.client_id == client_id).first()

    output = None
    if client:
        output = client._asdict()

    return output


def get_client_cases(client_id: int):
    cases_list = Cases.query.with_entities(
        Cases.case_id.label('case_id'),
        Cases.case_uuid.label('case_uuid'),
        Cases.name.label('case_name'),
        Cases.description.label('case_description'),
        Cases.status_id.label('case_status'),
        User.name.label('case_owner'),
        Cases.open_date,
        Cases.close_date
    ).filter(
        Cases.client_id == client_id,
    ).join(
        Cases.user
    ).all()

    return cases_list


def get_client_contacts(client_id: int) -> List[Contact]:
    contacts = Contact.query.filter(
        Contact.client_id == client_id
    ).order_by(
        Contact.contact_name
    ).all()

    return contacts


def get_client_contact(contact_id: int) -> Contact:
    contact = Contact.query.filter(
        Contact.id == contact_id
    ).first()

    return contact


def delete_contact(contact: Contact):
    try:
        db_delete(contact)
    except Exception:
        raise ElementInUseError('A currently referenced contact cannot be deleted')


def delete_client(customer: Client) -> None:
    try:
        db_delete(customer)
    except Exception:
        raise ElementInUseError('Cannot delete a referenced customer')


def get_case_client(case_id: int) -> Client:
    client = Cases.query.filter(case_id == case_id).with_entities(
        Cases.client_id
    ).first()

    return client


def get_customer_by_name(name, case_insensitive=False) -> Client:
    query = db.session.query(Client)
    if case_insensitive:
        query = query.filter(func.upper(Client.name) == name.upper())
    else:
        query = query.filter_by(name=name)
    return query.first()
