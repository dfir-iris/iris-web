#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

from sqlalchemy import and_
from sqlalchemy import or_

from app.models.cases import Cases
from app.models.customers import Client
from app.models.evidences import CaseReceivedFile


def search_evidences(search_value, accessible_case_ids=None):
    # Mirrors `search_iocs` / `search_notes` / `search_comments`: flat
    # `_asdict()` rows, optional access scoping via `accessible_case_ids`.
    # Matches against filename, description, and hash so the same input
    # can find an evidence whether the user types a name or a checksum.
    if accessible_case_ids is not None and not accessible_case_ids:
        return []

    scope_filter = CaseReceivedFile.case_id.in_(accessible_case_ids) if accessible_case_ids is not None else and_()
    pattern = f'%{search_value}%'

    res = CaseReceivedFile.query.with_entities(
        CaseReceivedFile.id.label('evidence_id'),
        CaseReceivedFile.filename,
        CaseReceivedFile.file_description,
        CaseReceivedFile.file_hash,
        Cases.name.label('case_name'),
        Cases.case_id,
        Client.name.label('customer_name')
    ).filter(
        and_(
            or_(
                CaseReceivedFile.filename.ilike(pattern),
                CaseReceivedFile.file_description.ilike(pattern),
                CaseReceivedFile.file_hash.ilike(pattern)
            ),
            CaseReceivedFile.case_id == Cases.case_id,
            Client.client_id == Cases.client_id,
            scope_filter
        )
    ).all()

    return [row._asdict() for row in res]
