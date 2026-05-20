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

from app.blueprints.access_controls import ac_api_requires, ac_fast_check_current_user_has_case_access
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.business.iocs import iocs_update
from app.business.iocs import iocs_delete
from app.business.iocs import iocs_get
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import IocSchemaForAPIV2
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.rest.v2.iocs_routes.comments import iocs_comments_blueprint
from app.iris_engine.module_handler.module_handler import call_deprecated_on_preload_modules_hook
from app.schema.marshables import IocSchema


class IocsOperations:

    def __init__(self):
        self._schema = IocSchemaForAPIV2()

    def read(self, identifier):
        try:
            ioc = iocs_get(identifier)
            if not ac_fast_check_current_user_has_case_access(ioc.case_id,
                                                              [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=ioc.case_id)

            result = self._schema.dump(ioc)
            return response_api_success(result)
        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, identifier):
        try:
            ioc = iocs_get(identifier)
            if not ac_fast_check_current_user_has_case_access(ioc.case_id,
                                                              [CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=ioc.case_id)

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

    def delete(self, identifier):
        try:
            ioc = iocs_get(identifier)
            if not ac_fast_check_current_user_has_case_access(ioc.case_id, [CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=ioc.case_id)

            iocs_delete(ioc)
            return response_api_deleted()

        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())


iocs_blueprint = Blueprint('iocs_rest_v2',
                           __name__,
                           url_prefix='/iocs')
iocs_blueprint.register_blueprint(iocs_comments_blueprint)
iocs_operations = IocsOperations()


@iocs_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_case_ioc(identifier):
    return iocs_operations.read(identifier)


@iocs_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_ioc(identifier):
    return iocs_operations.update(identifier)


@iocs_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_case_ioc(identifier):
    return iocs_operations.delete(identifier)
