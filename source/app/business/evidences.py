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

from flask_login import current_user
from marshmallow.exceptions import ValidationError

from app.business.errors import BusinessProcessingError
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import CaseEvidenceSchema
from app.models.models import CaseReceivedFile
from app.datamgmt.case.case_rfiles_db import add_rfile


def _load(request_data):
    try:
        evidence_schema = CaseEvidenceSchema()
        return evidence_schema.load(request_data)
    except ValidationError as e:
        raise BusinessProcessingError('Data error', data=e.messages)


def evidences_create(case_identifier, request_json) -> CaseReceivedFile:
    request_data = call_modules_hook('on_preload_evidence_create', data=request_json, caseid=case_identifier)

    evidence = _load(request_data)

    crf = add_rfile(evidence=evidence, user_id=current_user.id, caseid=case_identifier)

    crf = call_modules_hook('on_postload_evidence_create', data=crf, caseid=case_identifier)
    if not crf:
        raise BusinessProcessingError('Unable to create evidence for internal reasons')

    track_activity(f'added evidence "{crf.filename}"', caseid=case_identifier)
    return crf

