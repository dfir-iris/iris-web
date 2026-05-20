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

from app.datamgmt.db_operations import db_create
from app.datamgmt.manage.manage_organisations import get_organisation_by_name
from app.models.authorization import Organisation
from app.models.errors import ObjectNotFoundError


def organisations_get(name) -> Organisation:
    organisation = get_organisation_by_name(name)
    if not organisation:
        raise ObjectNotFoundError()
    return organisation


def organisations_create(name, description) -> Organisation:
    organisation = Organisation(org_name=name, org_description=description)
    db_create(organisation)
    return organisation
