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
from app.business.permissions import permissions_check_current_user_has_some_case_access
from app.datamgmt.case.case_assets_db import get_asset
from app.datamgmt.case.case_assets_db import create_asset
from app.datamgmt.case.case_assets_db import set_ioc_links
from app.datamgmt.case.case_assets_db import get_linked_iocs_finfo_from_asset
from app.datamgmt.case.case_assets_db import delete_asset
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models import CaseAssets
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import CaseAssetsSchema


def _load(request_data):
    try:
        add_assets_schema = CaseAssetsSchema()
        return add_assets_schema.load(request_data)
    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)


def assets_create(case_identifier, request_json):
    request_data = call_modules_hook('on_preload_asset_create', data=request_json, caseid=case_identifier)
    asset = _load(request_data)
    asset = create_asset(asset=asset, caseid=case_identifier, user_id=current_user.id)
    if request_data.get('ioc_links'):
        errors, _ = set_ioc_links(request_data.get('ioc_links'), asset.asset_id)
        if errors:
            raise BusinessProcessingError('Encountered errors while linking IOC. Asset has still been updated.')
    asset = call_modules_hook('on_postload_asset_create', data=asset, caseid=case_identifier)
    if asset:
        track_activity(f"added asset \"{asset.asset_name}\"", caseid=case_identifier)
        return 'Asset added', asset

    raise BusinessProcessingError("Unable to create asset for internal reasons")


def assets_delete(identifier):
    call_modules_hook('on_preload_asset_delete', data=identifier)
    asset = assets_get(identifier)
    permissions_check_current_user_has_some_case_access(asset.case_id, [CaseAccessLevel.full_access])

    # Deletes an asset and the potential links with the IoCs from the database
    delete_asset(identifier, asset.case_id)
    call_modules_hook('on_postload_asset_delete', data=identifier, caseid=asset.case_id)
    track_activity(f'removed asset ID {asset.asset_name}', caseid=asset.case_id)


def assets_get(identifier) -> CaseAssets:
    asset = get_asset(identifier)
    if not asset:
        raise BusinessProcessingError('Invalid asset ID for this case')

    return asset


def assets_get_detailed(identifier):
    asset = assets_get(identifier)

    # TODO this is a code smell: shouldn't have schemas in the business layer + the CaseAssetsSchema is instantiated twice
    case_assets_schema = CaseAssetsSchema()
    data = case_assets_schema.dump(asset)

    asset_iocs = get_linked_iocs_finfo_from_asset(identifier)
    data['linked_ioc'] = [row._asdict() for row in asset_iocs]
    return data