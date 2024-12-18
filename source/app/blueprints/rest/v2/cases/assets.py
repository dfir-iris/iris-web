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
from kombu.abstract import Object

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_not_found
from app.business.cases import cases_exists
from app.business.assets import assets_create, get_assets_case
from app.business.assets import assets_delete
from app.business.assets import assets_get
from app.business.errors import BusinessProcessingError
from app.business.errors import ObjectNotFoundError
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import CaseAssetsSchema
from app.blueprints.access_controls import ac_api_return_access_denied

case_assets_bp = Blueprint('case_assets',
                           __name__,
                           url_prefix='/<int:case_id>/assets')


@case_assets_bp.get('', strict_slashes=False)
@ac_api_requires()
def case_list_assets(case_id):
    """
    Returns the list of assets from the case. 

    Args:
        case_id (int): The ID of the case this asset belongs too

    Returns:
        A JSON object containing the assets of the case, enhanced with assets seen on other cases.
    """
    try:

        if not ac_fast_check_current_user_has_case_access(case_id, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_id)

        assets = get_assets_case(case_identifier=case_id)

        return response_api_success(data=assets)

    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())


@case_assets_bp.post('', strict_slashes=False)
@ac_api_requires()
def add_asset(case_id):
    """
    Adds a new asset to a case

    Args:
        case_id (int): The ID of the case this asset is for
    """
    if not cases_exists(case_id):
        return response_api_not_found()
    if not ac_fast_check_current_user_has_case_access(case_id, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=case_id)

    asset_schema = CaseAssetsSchema()
    try:
        _, asset = assets_create(case_id, request.get_json())
        return response_api_created(asset_schema.dump(asset))
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())


@case_assets_bp.get('/<int:identifier>')
@ac_api_requires()
def get_asset(case_id, identifier):
    """
    Get an asset by case ID & asset ID

    Args:
        case_id (int): The ID of the case this asset belongs too
        identifier (int): The asset ID to get
    """
    asset_schema = CaseAssetsSchema()

    try:
        asset = assets_get(identifier)

        # check asset & case ID match
        if asset.case_id != case_id:
            return response_api_not_found()

        # perform authz check
        if not ac_fast_check_current_user_has_case_access(asset.case_id, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=asset.case_id)

        return response_api_success(asset_schema.dump(asset))
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())


@case_assets_bp.delete('/<int:identifier>')
@ac_api_requires()
def delete_asset(case_id, identifier):
    """
    Handles deleting an asset by case ID & asset ID

    Args:
        case_id (int): The ID of the case this asset belongs too
        identifier (int): The asset ID to delete
    """
    try:
        asset = assets_get(identifier)

        # check asset & case ID match
        if asset.case_id != case_id:
            return response_api_not_found()

        # perform authz check
        if not ac_fast_check_current_user_has_case_access(asset.case_id, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=asset.case_id)

        assets_delete(asset)
        return response_api_deleted()
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
