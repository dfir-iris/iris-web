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

from flask import Blueprint
from flask import request

from app.blueprints.access_controls import ac_api_requires
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.models.authorization import CaseAccessLevel
from app.business.errors import BusinessProcessingError
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.business.cases import cases_exists
from app.schema.marshables import CaseEvidenceSchema
from app.business.evidences import evidences_create


case_evidences_blueprint = Blueprint('case_evidences_rest_v2', __name__, url_prefix='/<int:case_identifier>/evidences')


@case_evidences_blueprint.post('')
@ac_api_requires()
def create_evidence(case_identifier):

    if not cases_exists(case_identifier):
        return response_api_not_found()
    if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=case_identifier)

    try:
        evidence = evidences_create(case_identifier, request.get_json())

        evidence_schema = CaseEvidenceSchema()
        return response_api_created(evidence_schema.dump(evidence))
    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())
