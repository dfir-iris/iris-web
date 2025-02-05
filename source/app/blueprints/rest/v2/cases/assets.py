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
from app.blueprints.rest.endpoints import response_api_created, response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.business.cases import cases_exists
from app.business.assets import assets_create
from app.business.assets import assets_filter
from app.business.assets import assets_get
from app.business.assets import assets_update
from app.business.assets import assets_delete
from app.business.errors import BusinessProcessingError
from app.business.errors import ObjectNotFoundError
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import CaseAssetsSchema
from app.blueprints.access_controls import ac_api_return_access_denied

case_assets_blueprint = Blueprint('case_assets',
                                  __name__,
                                  url_prefix='/<int:case_identifier>/assets')


@case_assets_blueprint.get('')
@ac_api_requires()
def case_list_assets(case_identifier):

    try:

        if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        pagination_parameters = parse_pagination_parameters(request)

        assets = assets_filter(case_identifier, pagination_parameters)

        asset_schema = CaseAssetsSchema()
        return response_api_paginated(asset_schema, assets)

    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())


@case_assets_blueprint.post('')
@ac_api_requires()
def add_asset(case_identifier):

    if not cases_exists(case_identifier):
        return response_api_not_found()
    if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=case_identifier)

    asset_schema = CaseAssetsSchema()
    try:
        _, asset = assets_create(case_identifier, request.get_json())
        return response_api_created(asset_schema.dump(asset))
    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), e.get_data())


@case_assets_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_asset(case_identifier, identifier):

    asset_schema = CaseAssetsSchema()

    try:
        asset = assets_get(identifier)
        _check_asset_and_case_identifier_match(asset, case_identifier)

        # perform authz check
        if not ac_fast_check_current_user_has_case_access(asset.case_id, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=asset.case_id)

        return response_api_success(asset_schema.dump(asset))
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())


@case_assets_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_asset(case_identifier, identifier):
    try:
        asset = assets_get(identifier)
        _check_asset_and_case_identifier_match(asset, case_identifier)

        if not ac_fast_check_current_user_has_case_access(asset.case_id,[CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=asset.case_id)

        asset = assets_update(asset, request.get_json())

        asset_schema = CaseAssetsSchema()
        result = asset_schema.dump(asset)
        return response_api_success(result)

    except ObjectNotFoundError:
        return response_api_not_found()

    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())


@case_assets_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_asset(case_identifier, identifier):

    try:
        asset = assets_get(identifier)
        _check_asset_and_case_identifier_match(asset, case_identifier)

        # perform authz check
        if not ac_fast_check_current_user_has_case_access(asset.case_id, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=asset.case_id)

        assets_delete(asset)
        return response_api_deleted()
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())


def _check_asset_and_case_identifier_match(asset, case_identifier):
    if asset.case_id != case_identifier:
        raise ObjectNotFoundError
