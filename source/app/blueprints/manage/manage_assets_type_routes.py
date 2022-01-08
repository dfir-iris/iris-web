#!/usr/bin/env python3
#
#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
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

# IMPORTS ------------------------------------------------
from flask import Blueprint
from flask import render_template, request, url_for, redirect

from app.iris_engine.utils.tracker import track_activity
from app.models.models import AssetsType, CaseAssets
from app.forms import AddAssetForm
from app import db

from app.util import response_success, response_error, login_required, admin_required, api_admin_required

manage_assets_blueprint = Blueprint('manage_assets',
                                    __name__,
                                    template_folder='templates')


# CONTENT ------------------------------------------------
@manage_assets_blueprint.route('/manage/asset-type')
@admin_required
def manage_assets(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_assets.manage_assets', cid=caseid))

    form = AddAssetForm()

    # Return default page of case management
    return render_template('manage_assets.html', form=form)


@manage_assets_blueprint.route('/manage/asset-type/list')
@api_admin_required
def list_assets(caseid):
    # Get all assets
    assets = AssetsType.query.with_entities(
        AssetsType.asset_name,
        AssetsType.asset_description,
        AssetsType.asset_id
    ).all()

    data = [row._asdict() for row in assets]

    # Return the assets
    return response_success("", data=data)


@manage_assets_blueprint.route('/manage/asset-type/update/<int:cur_id>/modal', methods=['GET'])
@login_required
def view_assets_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_assets.manage_assets', cid=caseid))

    form = AddAssetForm()
    asset = AssetsType.query.filter(AssetsType.asset_id == cur_id).first()
    if not asset:
        return response_error("Invalid asset type ID")

    form.asset_name.render_kw = {'value': asset.asset_name}
    form.asset_description.render_kw = {'value': asset.asset_description}

    return render_template("modal_add_asset_type.html", form=form, assettype=asset)


@manage_assets_blueprint.route('/manage/asset-type/update/<int:cur_id>', methods=['POST'])
@api_admin_required
def view_assets(cur_id, caseid):
    if not request.is_json:
        return response_error("Invalid request")

    asset = AssetsType.query.filter(AssetsType.asset_id == cur_id).first()
    if not asset:
        return response_error("Invalid asset type ID")

    asset.asset_name = request.json.get('asset_name')
    asset.asset_description = request.json.get('asset_description')

    db.session.commit()

    return response_success("Asset type updated", data=asset)


@manage_assets_blueprint.route('/manage/asset-type/add/modal', methods=['GET'])
@admin_required
def add_assets_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_assets.manage_assets', cid=caseid))
    form = AddAssetForm()

    return render_template("modal_add_asset_type.html", form=form, assettype=None)


@manage_assets_blueprint.route('/manage/asset-type/add', methods=['POST'])
@api_admin_required
def add_assets(caseid):
    if not request.is_json:
        return response_error("Invalid request")

    asset_name = request.json.get('asset_name')
    asset_description = request.json.get('asset_description')

    asset = AssetsType(asset_name=asset_name,
                       asset_description=asset_description
                       )

    db.session.add(asset)
    db.session.commit()

    track_activity("Added asset type {asset_name}".format(asset_name=asset.asset_name), caseid=caseid, ctx_less=True)
    # Return the assets
    return response_success("Added successfully", data=asset)


@manage_assets_blueprint.route('/manage/asset-type/delete/<int:cur_id>', methods=['GET'])
@api_admin_required
def delete_assets(cur_id, caseid):
    asset = AssetsType.query.filter(AssetsType.asset_id == cur_id).first()
    if not asset:
        return response_error("Invalid asset ID")

    case_linked = CaseAssets.query.filter(CaseAssets.asset_type_id == cur_id).first()
    if case_linked:
        return response_error("Cannot delete a referenced asset type. Please delete any assets of this type first.")

    db.session.delete(asset)
    track_activity("Deleted asset type ID {asset_id}".format(asset_id=cur_id), caseid=caseid, ctx_less=True)

    return response_success("Deleted asset type ID {cur_id} successfully".format(cur_id=cur_id))
