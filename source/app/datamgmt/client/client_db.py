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
import marshmallow
from sqlalchemy import func, and_
from typing import List

from app import db
from app.datamgmt.exceptions.ElementExceptions import ElementInUseException
from app.datamgmt.exceptions.ElementExceptions import ElementNotFoundException
from app.models import Cases
from app.models import Client
from app.models import Contact
from app.models.authorization import User, UserClient
from app.schema.marshables import ContactSchema
from app.schema.marshables import CustomerSchema


def get_client_list(current_user_id: int = None,
                    is_server_administrator: bool = False) -> List[dict]:
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


def get_client(client_id: int) -> Client:
    client = Client.query.filter(Client.client_id == client_id).first()
    return client


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


def create_client(data) -> Client:

    client_schema = CustomerSchema()
    client = client_schema.load(data)

    db.session.add(client)
    db.session.commit()

    return client


def get_client_contacts(client_id: int) -> List[Contact]:
    contacts = Contact.query.filter(
        Contact.client_id == client_id
    ).order_by(
        Contact.contact_name
    ).all()

    return contacts


def get_client_contact(client_id: int, contact_id: int) -> Contact:
    contact = Contact.query.filter(
        Contact.client_id == client_id,
        Contact.id == contact_id
    ).first()

    return contact


def delete_contact(contact_id: int) -> None:
    contact = Contact.query.filter(
        Contact.id == contact_id
    ).first()

    if not contact:
        raise ElementNotFoundException('No Contact found with this uuid.')

    try:

        db.session.delete(contact)
        db.session.commit()

    except Exception as e:
        raise ElementInUseException('A currently referenced contact cannot be deleted')


def create_contact(data, customer_id) -> Contact:
    data['client_id'] = customer_id
    contact_schema = ContactSchema()
    contact = contact_schema.load(data)

    db.session.add(contact)
    db.session.commit()

    return contact


def update_contact(data, contact_id, customer_id) -> Contact:
    contact = get_client_contact(customer_id, contact_id)
    data['client_id'] = customer_id
    contact_schema = ContactSchema()
    contact_schema.load(data, instance=contact)

    db.session.commit()

    return contact


def update_client(client_id: int, data) -> Client:
    # TODO: Possible reuse somewhere else ...
    client = get_client(client_id)

    if not client:
        raise ElementNotFoundException('No Customer found with this uuid.')

    exists = Client.query.filter(
        Client.client_id != client_id,
        func.lower(Client.name) == data.get('customer_name').lower()
    ).first()

    if exists:
        raise marshmallow.exceptions.ValidationError(
            "Customer already exists",
            field_name="customer_name"
        )

    client_schema = CustomerSchema()
    client_schema.load(data, instance=client)

    db.session.commit()

    return client


def delete_client(client_id: int) -> None:
    client = Client.query.filter(
        Client.client_id == client_id
    ).first()

    if not client:
        raise ElementNotFoundException('No Customer found with this uuid.')

    try:

        db.session.delete(client)
        db.session.commit()

    except Exception as e:
        raise ElementInUseException('A currently referenced customer cannot be deleted')


def get_case_client(case_id: int) -> Client:
    client = Cases.query.filter(case_id == case_id).with_entities(
        Cases.client_id
    ).first()

    return client
