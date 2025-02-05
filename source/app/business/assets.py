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
from flask_sqlalchemy.pagination import Pagination

from app import db
from app.business.errors import BusinessProcessingError
from app.business.errors import ObjectNotFoundError
from app.business.cases import cases_exists
from app.datamgmt.case.case_db import get_case_client_id
from app.datamgmt.manage.manage_users_db import get_user_cases_fast
from app.datamgmt.states import get_assets_state
from app.datamgmt.states import update_assets_state
from app.models.models import CaseAssets
from app.models.pagination_parameters import PaginationParameters
from app.datamgmt.case.case_assets_db import get_asset
from app.datamgmt.case.case_assets_db import get_assets
from app.datamgmt.case.case_assets_db import filter_assets
from app.datamgmt.case.case_assets_db import get_assets_ioc_links
from app.datamgmt.case.case_assets_db import get_similar_assets
from app.datamgmt.case.case_assets_db import case_assets_db_exists
from app.datamgmt.case.case_assets_db import create_asset
from app.datamgmt.case.case_assets_db import set_ioc_links
from app.datamgmt.case.case_assets_db import get_linked_iocs_finfo_from_asset
from app.datamgmt.case.case_assets_db import delete_asset
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import CaseAssetsSchema


def _load(request_data, **kwargs):
    try:
        add_assets_schema = CaseAssetsSchema()
        return add_assets_schema.load(request_data, **kwargs)
    except ValidationError as e:
        raise BusinessProcessingError('Data error', data=e.messages)


def assets_create(case_identifier, request_json):
    request_data = call_modules_hook('on_preload_asset_create', data=request_json, caseid=case_identifier)
    asset = _load(request_data)
    asset.case_id = case_identifier

    if case_assets_db_exists(asset):
        raise BusinessProcessingError('Asset with same value and type already exists')
    asset = create_asset(asset=asset, caseid=case_identifier, user_id=current_user.id)
    # TODO should the custom attributes be set?
    if request_data.get('ioc_links'):
        errors, _ = set_ioc_links(request_data.get('ioc_links'), asset.asset_id)
        if errors:
            raise BusinessProcessingError('Encountered errors while linking IOC. Asset has still been created.')
    asset = call_modules_hook('on_postload_asset_create', data=asset, caseid=case_identifier)
    if asset:
        track_activity(f'added asset "{asset.asset_name}"', caseid=case_identifier)
        return 'Asset added', asset

    raise BusinessProcessingError('Unable to create asset for internal reasons')


def assets_delete(asset: CaseAssets):
    call_modules_hook('on_preload_asset_delete', data=asset.asset_id)
    # Deletes an asset and the potential links with the IoCs from the database
    delete_asset(asset)
    call_modules_hook('on_postload_asset_delete', data=asset.asset_id, caseid=asset.case_id)
    track_activity(f'removed asset ID {asset.asset_name}', caseid=asset.case_id)


def assets_get(identifier) -> CaseAssets:
    asset = get_asset(identifier)
    if not asset:
        raise ObjectNotFoundError()

    return asset


def assets_get_detailed(identifier):
    asset = assets_get(identifier)

    # TODO this is a code smell: shouldn't have schemas in the business layer + the CaseAssetsSchema is instantiated twice
    case_assets_schema = CaseAssetsSchema()
    data = case_assets_schema.dump(asset)

    asset_iocs = get_linked_iocs_finfo_from_asset(identifier)
    data['linked_ioc'] = [row._asdict() for row in asset_iocs]
    return data


def get_assets_case(case_identifier):
    assets = get_assets(case_identifier)
    customer_id = get_case_client_id(case_identifier)

    ret = {'assets': []}

    ioc_links_req = get_assets_ioc_links(case_identifier)

    cache_ioc_link = {}
    for ioc in ioc_links_req:

        if ioc.asset_id not in cache_ioc_link:
            cache_ioc_link[ioc.asset_id] = [ioc._asdict()]
        else:
            cache_ioc_link[ioc.asset_id].append(ioc._asdict())

    cases_access = get_user_cases_fast(current_user.id)

    for asset in assets:
        asset = asset._asdict()

        if len(assets) < 300:
            # Find similar assets from other cases with the same customer
            asset['link'] = list(get_similar_assets(
                asset['asset_name'], asset['asset_type_id'], case_identifier, customer_id, cases_access))
        else:
            asset['link'] = []

        asset['ioc_links'] = cache_ioc_link.get(asset['asset_id'])

        ret['assets'].append(asset)

    ret['state'] = get_assets_state(case_identifier)
    return ret


def assets_filter(case_identifier, pagination_parameters: PaginationParameters) -> Pagination:
    if not cases_exists(case_identifier):
        raise ObjectNotFoundError()
    return filter_assets(case_identifier, pagination_parameters)


def assets_update(asset: CaseAssets, request_json):
    caseid = asset.case_id
    request_data = call_modules_hook('on_preload_asset_update', data=request_json, caseid=caseid)

    request_data['asset_id'] = asset.asset_id

    asset_schema = _load(request_data, instance=asset)

    if case_assets_db_exists(asset_schema):
        raise BusinessProcessingError('Data error', data='Asset with same value and type already exists')

    update_assets_state(caseid=caseid)
    db.session.commit()

    if hasattr(asset_schema, 'ioc_links'):
        errors, _ = set_ioc_links(asset_schema.ioc_links, asset.asset_id)
        if errors:
            raise BusinessProcessingError('Encountered errors while linking IOC. Asset has still been updated.')

    asset_schema = call_modules_hook('on_postload_asset_update', data=asset_schema, caseid=caseid)

    if asset_schema:
        track_activity(f'updated asset "{asset_schema.asset_name}"', caseid=caseid)
        return asset_schema

    raise BusinessProcessingError('Unable to update asset for internal reasons')
