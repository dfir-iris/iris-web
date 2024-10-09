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

import logging as log
from flask import Blueprint
from flask import request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.business.errors import BusinessProcessingError
from app.business.errors import ObjectNotFoundError
from app.business.iocs import iocs_create, iocs_update
from app.business.iocs import iocs_delete
from app.business.iocs import iocs_get
from app.datamgmt.case.case_iocs_db import get_filtered_iocs
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import IocSchemaForAPIV2
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.responses import response_success
from app.blueprints.responses import response_error

api_v2_ioc_blueprint = Blueprint('case_ioc_rest_v2',
                                 __name__,
                                 url_prefix='/api/v2')


@api_v2_ioc_blueprint.route('/cases/<int:identifier>/iocs', methods=['GET'])
@ac_api_requires()
def list_ioc(identifier):
    if not ac_fast_check_current_user_has_case_access(identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=identifier)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    order_by = request.args.get('order_by', type=str)
    sort_dir = request.args.get('sort_dir', 'asc', type=str)

    ioc_type_id = request.args.get('ioc_type_id', None, type=int)
    ioc_type = request.args.get('ioc_type', None, type=str)
    ioc_tlp_id = request.args.get('ioc_tlp_id', None, type=int)
    ioc_value = request.args.get('ioc_value', None, type=str)
    ioc_description = request.args.get('ioc_description', None, type=str)
    ioc_tags = request.args.get('ioc_tags', None, type=str)

    filtered_iocs = get_filtered_iocs(
        caseid=identifier,
        ioc_type_id=ioc_type_id,
        ioc_type=ioc_type,
        ioc_tlp_id=ioc_tlp_id,
        ioc_value=ioc_value,
        ioc_description=ioc_description,
        ioc_tags=ioc_tags,
        page=page,
        per_page=per_page,
        sort_by=order_by,
        sort_dir=sort_dir
    )

    if filtered_iocs is None:
        return response_api_error('Filtering error')

    iocs = IocSchemaForAPIV2().dump(filtered_iocs.items, many=True)

    iocs = {
        'total': filtered_iocs.total,
        'data': iocs,
        'last_page': filtered_iocs.pages,
        'current_page': filtered_iocs.page,
        'next_page': filtered_iocs.next_num if filtered_iocs.has_next else None,
    }

    return response_api_success(data=iocs)


@api_v2_ioc_blueprint.route('/cases/<int:identifier>/iocs', methods=['POST'])
@ac_api_requires()
def case_add_ioc(identifier):
    if not ac_fast_check_current_user_has_case_access(identifier, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=identifier)

    ioc_schema = IocSchemaForAPIV2()

    try:
        ioc, _ = iocs_create(request.get_json(), identifier)
        return response_api_created(ioc_schema.dump(ioc))
    except BusinessProcessingError as e:
        log.error(e)
        return response_api_error(e.get_message())


@api_v2_ioc_blueprint.route('/iocs/<int:identifier>', methods=['DELETE'])
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


@api_v2_ioc_blueprint.route('/iocs/<int:identifier>', methods=['GET'])
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


@api_v2_ioc_blueprint.route('/iocs/<int:identifier>', methods=['POST'])
@ac_api_requires()
def update_ioc(identifier):
    ioc_schema = IocSchemaForAPIV2()
    try:
        #TODO: We have a useless double get on the IOC object
        # one for the access right, another one for the update of the object.
        ioc = iocs_get(identifier)
        if not ac_fast_check_current_user_has_case_access(ioc.case_id,
                                                          [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=ioc.case_id)

        try:
            ioc, msg = iocs_update(identifier, request.get_json())
            return response_success(msg, data=ioc_schema.dump(ioc))
        except BusinessProcessingError as e:
            return response_error(e.get_message(), data=e.get_data())

    except ObjectNotFoundError:
        return response_api_not_found()

