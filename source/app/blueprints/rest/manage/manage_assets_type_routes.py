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

import logging
import marshmallow
import os

from flask import Blueprint
from flask import request

from app import app
from app.db import db
from app.datamgmt.manage.manage_case_objs import search_asset_type_by_name
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.models.assets import AssetsType, CaseAssets
from app.schema.marshables import AssetTypeSchema
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success

manage_assets_type_rest_blueprint = Blueprint('manage_assets_type_rest', __name__)


@manage_assets_type_rest_blueprint.route('/manage/asset-type/list')
@ac_api_requires()
def list_assets():
    # Get all assets
    assets = AssetsType.query.with_entities(
        AssetsType.asset_name,
        AssetsType.asset_description,
        AssetsType.asset_id,
        AssetsType.asset_icon_compromised,
        AssetsType.asset_icon_not_compromised,
    ).all()

    data = []
    for row in assets:
        row_dict = row._asdict()
        row_dict['asset_icon_compromised_path'] = os.path.join(app.config['ASSET_SHOW_PATH'], row_dict['asset_icon_compromised'])
        row_dict['asset_icon_not_compromised_path'] = os.path.join(app.config['ASSET_SHOW_PATH'], row_dict['asset_icon_not_compromised'])
        data.append(row_dict)

    # Return the assets
    return response_success("", data=data)


@manage_assets_type_rest_blueprint.route('/manage/asset-type/<int:cur_id>', methods=['GET'])
@ac_api_requires()
def view_asset_api(cur_id):
    # Get all assets
    asset_type = AssetsType.query.with_entities(
        AssetsType.asset_name,
        AssetsType.asset_description,
        AssetsType.asset_id
    ).filter(
        AssetsType.asset_id == cur_id
    ).first()

    if not asset_type:
        return response_error(f'Invalid asset type ID {cur_id}')

    # Return the assets
    return response_success("", data=asset_type._asdict())


@manage_assets_type_rest_blueprint.route('/manage/asset-type/update/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def view_assets(cur_id):
    asset_type = AssetsType.query.filter(AssetsType.asset_id == cur_id).first()
    if not asset_type:
        return response_error("Invalid asset type ID")

    asset_schema = AssetTypeSchema()
    try:

        asset_sc = asset_schema.load(request.form, instance=asset_type)
        fpath_nc = asset_schema.load_store_icon(request.files.get('asset_icon_not_compromised'),
                                                'asset_icon_not_compromised')

        fpath_c = asset_schema.load_store_icon(request.files.get('asset_icon_compromised'), 'asset_icon_compromised')

        if fpath_nc is not None:
            asset_sc.asset_icon_not_compromised = fpath_nc
        if fpath_c is not None:
            asset_sc.asset_icon_compromised = fpath_c

        if asset_sc:
            track_activity(f"updated asset type {asset_sc.asset_name}")
            return response_success("Asset type updated", asset_sc)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    return response_error("Unexpected error server-side. Nothing updated")


@manage_assets_type_rest_blueprint.route('/manage/asset-type/add', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def add_assets():
    asset_schema = AssetTypeSchema()
    try:

        asset_sc = asset_schema.load(request.form)
        fpath_nc = asset_schema.load_store_icon(request.files.get('asset_icon_not_compromised'),
                                                'asset_icon_not_compromised')

        fpath_c = asset_schema.load_store_icon(request.files.get('asset_icon_compromised'), 'asset_icon_compromised')

        if fpath_nc is not None:
            asset_sc.asset_icon_not_compromised = fpath_nc
        if fpath_c is not None:
            asset_sc.asset_icon_compromised = fpath_c

        if asset_sc:
            db.session.add(asset_sc)
            db.session.commit()

            track_activity(f"updated asset type {asset_sc.asset_name}")
            return response_success("Asset type updated", asset_sc)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    return response_error("Unexpected error server-side. Nothing updated")


@manage_assets_type_rest_blueprint.route('/manage/asset-type/delete/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def delete_assets(cur_id):
    asset = AssetsType.query.filter(AssetsType.asset_id == cur_id).first()
    if not asset:
        return response_error("Invalid asset ID")

    case_linked = CaseAssets.query.filter(CaseAssets.asset_type_id == cur_id).first()
    if case_linked:
        return response_error("Cannot delete a referenced asset type. Please delete any assets of this type first.")

    try:
        # not deleting icons for now because multiple asset_types might rely on the same icon

        # only delete icons if there is only one AssetType linked to it
        if len(AssetsType.query.filter(AssetsType.asset_icon_compromised == asset.asset_icon_compromised).all()) == 1:
            os.unlink(os.path.join(app.config['ASSET_STORE_PATH'], asset.asset_icon_compromised))
        if len(AssetsType.query.filter(
                AssetsType.asset_icon_not_compromised == asset.asset_icon_not_compromised).all()) == 1:
            os.unlink(os.path.join(app.config['ASSET_STORE_PATH'], asset.asset_icon_not_compromised))

    except Exception as e:
        logging.error(f"Unable to delete {e}")

    db.session.delete(asset)

    track_activity(f"Deleted asset type ID {cur_id}", ctx_less=True)

    return response_success(f"Deleted asset type ID {cur_id} successfully")


@manage_assets_type_rest_blueprint.route('/manage/asset-types/search', methods=['POST'])
@ac_api_requires()
def search_assets_type():
    """Searches for assets types in the database.

    This function searches for assets types in the database with a name that contains the specified search term.
    It returns a JSON response containing the matching assets types.

    Args:
        caseid: The ID of the case associated with the request.

    Returns:
        A JSON response containing the matching assets types.

    """
    if not request.is_json:
        return response_error("Invalid request")

    asset_type = request.json.get('asset_type')
    if asset_type is None:
        return response_error("Invalid asset type. Got None")

    exact_match = request.json.get('exact_match', False)

    # Search for assets types with a name that contains the specified search term
    assets_type = search_asset_type_by_name(asset_type, exact_match=exact_match)
    if not assets_type:
        return response_error("No asset types found")

    # Serialize the assets types and return them in a JSON response
    assetst_schema = AssetTypeSchema(many=True)
    return response_success("", data=assetst_schema.dump(assets_type))
