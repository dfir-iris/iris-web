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

from flask_sqlalchemy.pagination import Pagination

from app.db import db
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.business.cases import cases_exists
from app.datamgmt.states import update_assets_state
from app.models.assets import CaseAssets
from app.models.pagination_parameters import PaginationParameters
from app.datamgmt.case.case_assets_db import get_asset
from app.datamgmt.case.case_assets_db import filter_assets
from app.datamgmt.case.case_assets_db import case_assets_db_exists
from app.datamgmt.case.case_assets_db import create_asset
from app.datamgmt.case.case_assets_db import set_ioc_links
from app.datamgmt.case.case_assets_db import delete_asset
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.util import add_obj_history_entry


def assets_create(user, case_identifier, asset: CaseAssets, ioc_links):
    asset.case_id = case_identifier

    if case_assets_db_exists(asset):
        raise BusinessProcessingError('Asset with same value and type already exists')
    asset = create_asset(asset=asset, caseid=case_identifier, user_id=user.id)
    # TODO should the custom attributes be set?
    if ioc_links:
        errors, _ = set_ioc_links(ioc_links, asset.asset_id)
        if errors:
            raise BusinessProcessingError('Encountered errors while linking IOC. Asset has still been created.')
    asset = call_modules_hook('on_postload_asset_create', asset, caseid=case_identifier)

    add_obj_history_entry(asset, 'created')

    if asset:
        track_activity(f'added asset "{asset.asset_name}"', caseid=case_identifier)
        return asset

    raise BusinessProcessingError('Unable to create asset for internal reasons')


def assets_delete(asset: CaseAssets):
    call_modules_hook('on_preload_asset_delete', asset.asset_id)
    # Deletes an asset and the potential links with the IoCs from the database
    delete_asset(asset)
    call_modules_hook('on_postload_asset_delete', asset.asset_id, caseid=asset.case_id)
    track_activity(f'removed asset ID {asset.asset_name}', caseid=asset.case_id)


def assets_get(identifier) -> CaseAssets:
    asset = get_asset(identifier)
    if not asset:
        raise ObjectNotFoundError()

    return asset


def assets_filter(case_identifier, pagination_parameters: PaginationParameters, request_parameters: dict) -> Pagination:
    if not cases_exists(case_identifier):
        raise ObjectNotFoundError()

    try:
        pagination = filter_assets(case_identifier, pagination_parameters, request_parameters)

        return pagination
    except Exception as e:
        raise BusinessProcessingError(str(e))


def assets_update(asset: CaseAssets):

    if case_assets_db_exists(asset):
        raise BusinessProcessingError('Data error', data='Asset with same value and type already exists')

    update_assets_state(asset.case_id)
    add_obj_history_entry(asset, 'updated')
    db.session.commit()

    if hasattr(asset, 'ioc_links'):
        errors, _ = set_ioc_links(asset.ioc_links, asset.asset_id)
        if errors:
            raise BusinessProcessingError('Encountered errors while linking IOC. Asset has still been updated.')

    asset = call_modules_hook('on_postload_asset_update', asset, caseid=asset.case_id)

    if asset:
        track_activity(f'updated asset "{asset.asset_name}"', caseid=asset.case_id)
        return asset

    raise BusinessProcessingError('Unable to update asset for internal reasons')
