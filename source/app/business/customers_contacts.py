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

from typing import List

from app.models.models import Contact
from app.models.errors import ObjectNotFoundError
from app.datamgmt.client.client_db import delete_contact
from app.datamgmt.client.client_db import get_client_contact
from app.datamgmt.client.client_db import get_client_contacts
from app.datamgmt.client.client_db import update_contact
from app.datamgmt.db_operations import db_create
from app.iris_engine.utils.tracker import track_activity


def customers_contacts_get(identifier) -> Contact:
    contact = get_client_contact(identifier)
    if not contact:
        raise ObjectNotFoundError()
    return contact


def customers_contacts_list(client_id: int) -> List[Contact]:
    """Return every contact bound to a given customer, sorted by name.

    The data layer enforces the sort so consumers don't need to —
    contacts are typically displayed in a directory-style list and a
    stable order across requests matters for pagination UX.
    """
    return get_client_contacts(client_id)


def customers_contacts_create(contact: Contact) -> Contact:
    db_create(contact)
    track_activity(f'Added contact {contact.contact_name}', ctx_less=True)
    return contact


def customers_contacts_update(contact: Contact) -> Contact:
    """Persist pending in-session edits on `contact`.

    Mirrors the legacy `update_contact()` helper — the caller has
    already mutated the SQLAlchemy instance (typically via
    `ContactSchema.load(..., instance=contact)`) so this just flushes
    the session.
    """
    update_contact()
    track_activity(f'Updated contact {contact.contact_name}', ctx_less=True)
    return contact


def customers_contacts_delete(contact: Contact) -> None:
    name = contact.contact_name
    delete_contact(contact)
    track_activity(f'Deleted contact {name}', ctx_less=True)
