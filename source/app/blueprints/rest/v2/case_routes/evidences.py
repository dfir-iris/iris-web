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
from marshmallow import ValidationError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.models.authorization import CaseAccessLevel
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.business.cases import cases_exists
from app.schema.marshables import CaseEvidenceSchema
from app.business.evidences import evidences_create
from app.business.evidences import evidences_get
from app.business.evidences import evidences_update
from app.business.evidences import evidences_filter
from app.business.evidences import evidences_delete
from app.iris_engine.module_handler.module_handler import call_deprecated_on_preload_modules_hook


class EvidencesOperations:

    def __init__(self):
        self._schema = CaseEvidenceSchema()

    @staticmethod
    def _get_evidence_in_case(identifier, case_identifier):
        evidence = evidences_get(identifier)
        if evidence.case_id != case_identifier:
            raise BusinessProcessingError(f'Evidence {evidence.id} does not belong to case {case_identifier}')
        return evidence

    def search(self, case_identifier):
        if not cases_exists(case_identifier):
            return response_api_not_found()

        if not ac_fast_check_current_user_has_case_access(case_identifier,
                                                          [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        pagination_parameters = parse_pagination_parameters(request, default_order_by='date_added',
                                                            default_direction='desc')
        try:
            evidences = evidences_filter(case_identifier, pagination_parameters)

            return response_api_paginated(self._schema, evidences)
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def create(self, case_identifier):

        if not cases_exists(case_identifier):
            return response_api_not_found()
        if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        try:
            request_data = call_deprecated_on_preload_modules_hook('evidence_create', request.get_json(),
                                                                   case_identifier)
            evidence = self._schema.load(request_data)

            evidence = evidences_create(case_identifier, evidence)
            return response_api_created(self._schema.dump(evidence))

        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)

        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def read(self, case_identifier, identifier):
        if not cases_exists(case_identifier):
            return response_api_not_found()

        try:
            evidence = self._get_evidence_in_case(identifier, case_identifier)

            if not ac_fast_check_current_user_has_case_access(evidence.case_id,
                                                              [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=evidence.case_id)

            return response_api_success(self._schema.dump(evidence))
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def update(self, case_identifier, identifier):
        if not cases_exists(case_identifier):
            return response_api_not_found()

        try:
            evidence = self._get_evidence_in_case(identifier, case_identifier)
            if not ac_fast_check_current_user_has_case_access(evidence.case_id, [CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=evidence.case_id)

            request_data = call_deprecated_on_preload_modules_hook('evidence_update', request.get_json(), evidence.case_id)
            request_data['id'] = evidence.id
            evidence = self._schema.load(request_data, instance=evidence, partial=True)

            evidence = evidences_update(evidence)

            result = self._schema.dump(evidence)
            return response_api_success(result)

        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def delete(self, case_identifier, identifier):
        if not cases_exists(case_identifier):
            return response_api_not_found()

        try:
            evidence = self._get_evidence_in_case(identifier, case_identifier)
            if not ac_fast_check_current_user_has_case_access(evidence.case_id, [CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=evidence.case_id)

            evidences_delete(evidence)

            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())


evidences_operations = EvidencesOperations()
case_evidences_blueprint = Blueprint('case_evidences_rest_v2', __name__, url_prefix='/<int:case_identifier>/evidences')


@case_evidences_blueprint.get('')
@ac_api_requires()
def search_evidences(case_identifier):
    return evidences_operations.search(case_identifier)


@case_evidences_blueprint.post('')
@ac_api_requires()
def create_evidence(case_identifier):
    return evidences_operations.create(case_identifier)


@case_evidences_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_evidence(case_identifier, identifier):
    return evidences_operations.read(case_identifier, identifier)


@case_evidences_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_evidence(case_identifier, identifier):
    return evidences_operations.update(case_identifier, identifier)


@case_evidences_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_evidence(case_identifier, identifier):
    return evidences_operations.delete(case_identifier, identifier)
