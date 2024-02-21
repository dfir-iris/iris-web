#  IRIS Source Code
#  Copyright (C) 2023 - DFIR-IRIS
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
from sqlalchemy import func

from app import db
from app.models.alerts import Severity


def get_severities_list():
    """
    Get a list of severities from the database

    returns:
        list: A list of severities
    """
    return db.session.query(Severity).distinct().all()


def get_severity_by_id(status_id: int) -> Severity:
    """
    Get a severity from the database by its ID

    args:
        status_id (int): The ID of the severity to retrieve

    returns:
        Severity: The severity object
    """
    return db.session.query(Severity).filter(Severity.severity_id == status_id).first()


def search_severity_by_name(name: str, exact_match: bool = True) -> Severity:
    """
    Search for a severity by its name

    args:
        name (str): The name of the severity to search for
        exact_match (bool): Whether to search for an exact match or not

    returns:
        Severity: The severity object
    """
    if exact_match:
        return db.session.query(Severity).filter(func.lower(Severity.severity_name) == name.lower()).all()

    return db.session.query(Severity).filter(Severity.severity_name.ilike(f'%{name}%')).all()
