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
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.business.errors import BusinessProcessingError
from app.business.errors import ObjectNotFoundError
from app.business.iocs import iocs_update
from app.business.iocs import iocs_delete
from app.business.iocs import iocs_get
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import IocSchemaForAPIV2
from app.blueprints.access_controls import ac_api_return_access_denied

iocs_blueprint = Blueprint('iocs_rest_v2',
                           __name__,
                           url_prefix='/iocs')


@iocs_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_case_ioc(identifier):

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


@iocs_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_case_ioc(identifier):
    ioc_schema = IocSchemaForAPIV2()
    try:
        ioc = iocs_get(identifier)
        if not ac_fast_check_current_user_has_case_access(ioc.case_id, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=ioc.case_id)

        return response_api_success(ioc_schema.dump(ioc))
    except ObjectNotFoundError:
        return response_api_not_found()


@iocs_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_ioc(identifier):
    ioc_schema = IocSchemaForAPIV2()
    try:
        ioc = iocs_get(identifier)
        if not ac_fast_check_current_user_has_case_access(ioc.case_id,
                                                          [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=ioc.case_id)

        ioc, _ = iocs_update(ioc, request.get_json())
        return response_api_success(ioc_schema.dump(ioc))

    except ObjectNotFoundError:
        return response_api_not_found()

    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())
