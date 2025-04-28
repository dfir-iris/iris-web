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

from marshmallow.exceptions import ValidationError
from flask_sqlalchemy.pagination import Pagination

from app.iris_engine.access_control.iris_user import iris_current_user
from app.business.errors import BusinessProcessingError
from app.business.errors import ObjectNotFoundError
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import CaseEvidenceSchema
from app.models.models import CaseReceivedFile
from app.models.pagination_parameters import PaginationParameters
from app.datamgmt.case.case_rfiles_db import add_rfile
from app.datamgmt.case.case_rfiles_db import delete_rfile
from app.datamgmt.case.case_rfiles_db import get_rfile
from app.datamgmt.case.case_rfiles_db import get_paginated_evidences
from app.datamgmt.case.case_rfiles_db import update_rfile


def _load(request_data, **kwargs):
    try:
        evidence_schema = CaseEvidenceSchema()
        return evidence_schema.load(request_data, **kwargs)
    except ValidationError as e:
        raise BusinessProcessingError('Data error', data=e.messages)


def evidences_create(case_identifier, request_json) -> CaseReceivedFile:
    request_data = call_modules_hook('on_preload_evidence_create', data=request_json, caseid=case_identifier)

    evidence = _load(request_data)

    crf = add_rfile(evidence=evidence, user_id=iris_current_user.id, caseid=case_identifier)

    crf = call_modules_hook('on_postload_evidence_create', data=crf, caseid=case_identifier)
    if not crf:
        raise BusinessProcessingError('Unable to create evidence for internal reasons')

    track_activity(f'added evidence "{crf.filename}"', caseid=case_identifier)
    return crf


def evidences_get(identifier) -> CaseReceivedFile:
    evidence = get_rfile(identifier)
    if not evidence:
        raise ObjectNotFoundError()
    return evidence


def evidences_update(evidence: CaseReceivedFile, request_json: dict) -> CaseReceivedFile:
    request_data = call_modules_hook('on_preload_evidence_update', data=request_json, caseid=evidence.case_id)
    request_data['id'] = evidence.id
    evidence = _load(request_data, instance=evidence, partial=True)
    evidence = update_rfile(evidence=evidence, user_id=iris_current_user.id, caseid=evidence.case_id)
    evidence = call_modules_hook('on_postload_evidence_update', data=evidence, caseid=evidence.case_id)
    if not evidence:
        raise BusinessProcessingError('Unable to update task for internal reasons')
    track_activity(f'updated evidence "{evidence.filename}"', caseid=evidence.case_id)
    return evidence


def evidences_filter(case_identifier, pagination_parameters: PaginationParameters) -> Pagination:
    order_by = pagination_parameters.get_order_by()
    if not hasattr(CaseReceivedFile, order_by):
        raise BusinessProcessingError(f'Unexpected order_by field {order_by}')
    return get_paginated_evidences(case_identifier, pagination_parameters)


def evidences_delete(evidence: CaseReceivedFile):
    call_modules_hook('on_preload_evidence_delete', data=evidence.id, caseid=evidence.case_id)
    delete_rfile(evidence)
    call_modules_hook('on_postload_evidence_delete', data=evidence.id, caseid=evidence.case_id)
    track_activity(f'deleted evidence "{evidence.filename}" from registry', evidence.case_id)
