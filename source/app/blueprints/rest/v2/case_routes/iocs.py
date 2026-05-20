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

from app.logger import logger
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.blueprints.rest.parsing import parse_fields_parameters
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.business.iocs import iocs_create
from app.business.iocs import iocs_get
from app.business.iocs import iocs_delete
from app.business.iocs import iocs_update
from app.business.iocs import iocs_filter
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import IocSchemaForAPIV2
from app.blueprints.access_controls import ac_api_return_access_denied
from app.models.iocs import Ioc
from app.iris_engine.module_handler.module_handler import call_deprecated_on_preload_modules_hook
from app.schema.marshables import IocSchema


class IocsOperations:

    def __init__(self):
        self._schema = IocSchemaForAPIV2()

    @staticmethod
    def _get_ioc_in_case(identifier, case_identifier) -> Ioc:
        ioc = iocs_get(identifier)
        if ioc.case_id != case_identifier:
            raise ObjectNotFoundError
        return ioc

    def search(self, case_identifier):
        try:
            if not ac_fast_check_current_user_has_case_access(case_identifier,
                                                              [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=case_identifier)

            pagination_parameters = parse_pagination_parameters(request)
            fields = parse_fields_parameters(request)

            filtered_iocs = iocs_filter(case_identifier, pagination_parameters, request.args.to_dict())

            if fields:
                iocs_schema = IocSchemaForAPIV2(only=fields)
            else:
                iocs_schema = self._schema

            return response_api_paginated(iocs_schema, filtered_iocs)

        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())

    def create(self, case_identifier):
        if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        try:
            request_data = call_deprecated_on_preload_modules_hook('ioc_create', request.get_json(), case_identifier)
            request_data['case_id'] = case_identifier

            ioc = self._schema.load(request_data)
            ioc = iocs_create(ioc)
            result = self._schema.dump(ioc)
            return response_api_created(result)
        except ValidationError as e:
            return response_api_error('Data error', e.messages)
        except BusinessProcessingError as e:
            logger.error(e)
            return response_api_error(e.get_message())

    def read(self, case_identifier, identifier):
        if not ac_fast_check_current_user_has_case_access(case_identifier,
                                                          [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        try:
            ioc = self._get_ioc_in_case(identifier, case_identifier)

            result = self._schema.dump(ioc)
            return response_api_success(result)
        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, case_identifier, identifier):
        if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        try:
            ioc = self._get_ioc_in_case(identifier, case_identifier)

            request_data = call_deprecated_on_preload_modules_hook('ioc_update', request.get_json(), ioc.case_id)

            # validate before saving
            ioc_schema = IocSchema()
            request_data['ioc_id'] = ioc.ioc_id
            request_data['case_id'] = ioc.case_id
            ioc_sc = ioc_schema.load(request_data, instance=ioc, partial=True)

            ioc = iocs_update(ioc, ioc_sc)

            result = self._schema.dump(ioc)
            return response_api_success(result)

        except ValidationError as e:
            return response_api_error('Data error', e.messages)

        except ObjectNotFoundError:
            return response_api_not_found()

        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def delete(self, case_identifier, identifier):
        if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        try:
            ioc = self._get_ioc_in_case(identifier, case_identifier)

            iocs_delete(ioc)
            return response_api_deleted()

        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())


case_iocs_blueprint = Blueprint('case_ioc_rest_v2',
                                __name__,
                                url_prefix='/<int:case_identifier>/iocs')
iocs_operations = IocsOperations()


@case_iocs_blueprint.get('')
@ac_api_requires()
def get_case_iocs(case_identifier):
    return iocs_operations.search(case_identifier)


@case_iocs_blueprint.post('')
@ac_api_requires()
def add_ioc_to_case(case_identifier):
    return iocs_operations.create(case_identifier)


@case_iocs_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_case_ioc(case_identifier, identifier):
    return iocs_operations.read(case_identifier, identifier)


@case_iocs_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_ioc(case_identifier, identifier):
    return iocs_operations.update(case_identifier, identifier)


@case_iocs_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_case_ioc(case_identifier, identifier):
    return iocs_operations.delete(case_identifier, identifier)
