#  IRIS Source Code
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
from typing import List

from app.models import EvidenceTypes, CaseReceivedFile


def get_evidence_types_list() -> List[dict]:
    """Get a list of evidence types

    Returns:
        List[dict]: List of evidence types
    """
    evidence_types = EvidenceTypes.query.with_entities(
        EvidenceTypes.id,
        EvidenceTypes.name,
        EvidenceTypes.description,
        EvidenceTypes.creation_date
    ).all()

    c_cl = [row._asdict() for row in evidence_types]
    return c_cl


def get_evidence_type_by_id(cur_id: int) -> EvidenceTypes:
    """Get an evidence type from its ID

    Args:
        cur_id (int): evidence type id

    Returns:
        EvidenceTypes: Evidence Type
    """
    evidence_type = EvidenceTypes.query.filter_by(id=cur_id).first()
    return evidence_type


def verify_evidence_type_in_use(cur_id: int) -> bool:
    """Returns true if the evidence type is in use

    Args:
        cur_id (int): Evidence type id to check

    Returns:
        Bool: True if in us
    """
    exists = CaseReceivedFile.query.filter(
        CaseReceivedFile.type_id == cur_id
    ).first()

    return exists is not None


def get_evidence_type_by_name(cur_name: str) -> EvidenceTypes:
    """Get an evidence type

    Args:
        cur_name (str): evidence type name

    Returns:
        EvidenceTypes: Evidence type
    """
    case_classification = EvidenceTypes.query.filter_by(name=cur_name).first()
    return case_classification


def search_evidence_type_by_name(name: str, exact_match: bool = False) -> List[dict]:
    """Search for an evidence type by name

    Args:
        name (str): evidence type name
        exact_match (bool, optional): Exact match. Defaults to False.

    Returns:
        List[dict]: List of evidence types
    """
    if exact_match:
        query_filter = (func.lower(EvidenceTypes.name) == name.lower())
    else:
        query_filter = (EvidenceTypes.name.ilike(f'%{name}%'))

    return EvidenceTypes.query.filter(query_filter).all()
