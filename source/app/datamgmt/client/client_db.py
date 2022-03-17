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
from sqlalchemy import JSON
from typing import List, Dict, Union

from app import db
from app.datamgmt.exceptions.ElementExceptions import ElementNotFoundException
from app.datamgmt.exceptions.ElementExceptions import ElementInUseException
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.models import Client
from app.schema.marshables import CustomerSchema


def get_client_list() -> List[Client]:
    client_list = Client.query.with_entities(
        Client.name.label('customer_name'),
        Client.client_id.label('customer_id')
    ).all()

    output = [c._asdict() for c in client_list]

    return output


def get_client(client_id: str) -> Client:
    client = Client.query.filter(Client.client_id == client_id).first()
    return client


def get_client_api(client_id: str) -> Client:
    client = Client.query.with_entities(
        Client.name.label('customer_name'),
        Client.client_id.label('customer_id')
    ).filter(Client.client_id == client_id).first()

    output = client._asdict()

    return output


def create_client(data) -> Client:

    client_schema = CustomerSchema()
    client = client_schema.load(data)

    db.session.add(client)
    db.session.commit()

    return client


def update_client(client_id: str, data) -> Client:
    # TODO: Possible reuse somewhere else ...
    client = get_client(client_id)

    if not client:
        raise ElementNotFoundException('No Customer found with this uuid.')

    client_schema = CustomerSchema()
    client_schema.load(data, instance=client)

    db.session.commit()

    return client


def delete_client(client_id: str) -> None:
    client = Client.query.filter(
        Client.client_id == client_id
    ).first()

    if not client:
        raise ElementNotFoundException('No Customer found with this uuid.')

    try:

        Client.query.filter(
            Client.client_id == client_id
        ).delete()
        db.session.commit()

    except Exception as e:
        raise ElementInUseException('A used customer cannot be deleted')


