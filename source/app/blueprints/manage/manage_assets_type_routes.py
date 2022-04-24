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
from cmath import log
import logging
import marshmallow, string, random
from flask import Blueprint, flash
from flask import render_template, request, url_for, redirect

from app.iris_engine.utils.tracker import track_activity
from app.models.models import AssetsType, CaseAssets
from app.forms import AddAssetForm
from app import db, app
from app.schema.marshables import AssetSchema
import os


from app.util import response_success, response_error, login_required, admin_required, api_admin_required, \
    api_login_required

manage_assets_blueprint = Blueprint('manage_assets',
                                    __name__,
                                    template_folder='templates')


ALLOWED_EXTENSIONS = {'png', 'svg'}

def store_icon(file, icon, asset_type):
    if file and allowed_file(file.filename):
        filename = get_random_string(18)

        try:
            store_fullpath = os.path.join(app.config['ASSET_STORE_PATH'], filename)
            show_fullpath = os.path.join(app.config['APP_PATH'],'app',app.config['ASSET_SHOW_PATH'].strip(os.path.sep),filename)
            file.save(store_fullpath)
            os.symlink(store_fullpath, show_fullpath)  
        except Exception as e:
            return response_error(f"Unable to add icon {e}")

        setattr(asset_type, icon, filename)
    

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_random_string(length):
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str


@manage_assets_blueprint.route('/manage/asset-type/list')
@api_login_required
def list_assets(caseid):
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
        row_dict['asset_icon_compromised_path'] = os.path.join(app.config['APP_PATH'],'app',app.config['ASSET_SHOW_PATH'].strip(os.path.sep),row_dict['asset_icon_compromised'])
        row_dict['asset_icon_not_compromised_path'] = os.path.join(app.config['APP_PATH'],'app',app.config['ASSET_SHOW_PATH'].strip(os.path.sep),row_dict['asset_icon_not_compromised'])
        data.append(row._asdict())
    # data = [row._asdict() for row in assets]

    # Return the assets
    return response_success("", data=data)


@manage_assets_blueprint.route('/manage/asset-type/<int:cur_id>', methods=['GET'])
@api_login_required
def view_asset_api(cur_id, caseid):
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
    form.asset_icon_compromised.render_kw = {'value': asset.asset_icon_compromised}
    form.asset_icon_not_compromised.render_kw = {'value': asset.asset_icon_not_compromised}
    setattr(asset, 'asset_icon_compromised_path', os.path.join(app.config['ASSET_SHOW_PATH'], asset.asset_icon_compromised))
    setattr(asset, 'asset_icon_not_compromised_path',os.path.join(app.config['ASSET_SHOW_PATH'], asset.asset_icon_not_compromised))


    return render_template("modal_add_asset_type.html", form=form, assettype=asset)


@manage_assets_blueprint.route('/manage/asset-type/update/<int:cur_id>', methods=['POST'])
@api_admin_required
def view_assets(cur_id, caseid):
    asset_type = AssetsType.query.filter(AssetsType.asset_id == cur_id).first()
    if not asset_type:
        return response_error("Invalid asset type ID")

    form = AddAssetForm()
    
    if form.is_submitted():
        
        asset_type.asset_name = request.form.get('asset_name','', type=str)
        asset_type.asset_description = request.form.get('asset_description','', type=str)
        for icon in ['asset_icon_compromised','asset_icon_not_compromised']:
            file = request.files[icon]

            store_icon(file, icon, asset_type)
            

        db.session.commit()
        track_activity("Updated asset type {asset_name}".format(asset_name=asset_type.asset_name), caseid=caseid, ctx_less=True)
    else:
        print("invalid")

    
    # Return the assets
    return response_success("Added successfully", data=asset_type.asset_name)


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

    form = AddAssetForm()

    asset_type = AssetsType()

    if form.is_submitted():
        
        asset_type.asset_name = request.form.get('asset_name','', type=str)
        asset_type.asset_description = request.form.get('asset_description','', type=str)
        for icon in ['asset_icon_compromised','asset_icon_not_compromised']:
            file = request.files[icon]

            store_icon(file, icon, asset_type)


        db.session.add(asset_type)
        db.session.commit()
        track_activity("Added asset type {asset_name}".format(asset_name=asset_type.asset_name), caseid=caseid, ctx_less=True)
    else:
        print("invalid")

    
    # Return the assets
    return response_success("Added successfully", data=asset_type.asset_name)


@manage_assets_blueprint.route('/manage/asset-type/delete/<int:cur_id>', methods=['GET'])
@api_admin_required
def delete_assets(cur_id, caseid):
    asset = AssetsType.query.filter(AssetsType.asset_id == cur_id).first()
    if not asset:
        return response_error("Invalid asset ID")

    case_linked = CaseAssets.query.filter(CaseAssets.asset_type_id == cur_id).first()
    if case_linked:
        return response_error("Cannot delete a referenced asset type. Please delete any assets of this type first.")

    
    try:
        #not deleting icons for now because multiple asset_types might rely on the same icon
        
        #only delete icons if there is only one AssetType linked to it
        if(len(AssetsType.query.filter(AssetsType.asset_icon_compromised == asset.asset_icon_compromised).all()) == 1):
            os.unlink(os.path.join(app.config['ASSET_STORE_PATH'], asset.asset_icon_compromised))
        if(len(AssetsType.query.filter(AssetsType.asset_icon_not_compromised == asset.asset_icon_not_compromised).all()) == 1):
            os.unlink(os.path.join(app.config['ASSET_STORE_PATH'], asset.asset_icon_not_compromised))

    except Exception as e:
        logging.error(f"Unable to delete {e}")
    
    db.session.delete(asset)

    track_activity("Deleted asset type ID {asset_id}".format(asset_id=cur_id), caseid=caseid, ctx_less=True)

    return response_success("Deleted asset type ID {cur_id} successfully".format(cur_id=cur_id))
