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
import marshmallow
from flask import Blueprint
from flask import render_template, url_for, redirect, request
from flask_login import current_user

from app import db
from app.datamgmt.case.case_assets_db import get_assets_types, delete_asset, get_assets, get_asset, \
    get_similar_assets, get_linked_iocs_from_asset, set_ioc_links, get_linked_iocs_id_from_asset, \
    create_asset, get_analysis_status_list, get_linked_iocs_finfo_from_asset
from app.datamgmt.case.case_db import get_case, get_case_client_id
from app.datamgmt.case.case_iocs_db import get_iocs
from app.datamgmt.states import get_assets_state, update_assets_state
from app.forms import ModalAddCaseAssetForm, AssetBasicForm

from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import CaseAssetsSchema
from app.util import response_success, response_error, login_required, api_login_required

case_assets_blueprint = Blueprint('case_assets',
                                  __name__,
                                  template_folder='templates')


@case_assets_blueprint.route('/case/assets', methods=['GET', 'POST'])
@login_required
def case_assets(caseid, url_redir):
    """
    Returns the page of case assets, with the list of available assets types.
    :return: The HTML page of case assets
    """
    if url_redir:
        return redirect(url_for('case_assets.case_assets', cid=caseid))

    form = ModalAddCaseAssetForm()
    # Get asset types from database
    form.asset_id.choices = get_assets_types()

    # Retrieve the assets linked to the investigation
    case = get_case(caseid)

    return render_template("case_assets.html", case=case, form=form)


@case_assets_blueprint.route('/case/assets/list', methods=['GET'])
@api_login_required
def case_list_assets(caseid):
    """
    Returns the list of assets from the case.
    :return: A JSON object containing the assets of the case, enhanced with assets seen on other cases.
    """

    # Get all assets objects from the case and the customer id
    assets = get_assets(caseid)
    customer_id = get_case_client_id(caseid)

    ret = {}
    ret['assets'] = []

    for asset in assets:
        asset = asset._asdict()

        # Find linked IoC
        iocs = get_linked_iocs_from_asset(asset["asset_id"])
        asset['ioc'] = [ioc for ioc in iocs]

        # Find similar assets from other cases with the same customer
        asset['link'] = [lasset._asdict() for lasset in get_similar_assets(
                        asset['asset_name'], asset['asset_type_id'], caseid, customer_id)]

        ret['assets'].append(asset)

    ret['state'] = get_assets_state(caseid=caseid)

    return response_success("", data=ret)


@case_assets_blueprint.route('/case/assets/state', methods=['GET'])
@api_login_required
def case_assets_state(caseid):
    os = get_assets_state(caseid=caseid)
    if os:
        return response_success(data=os)
    else:
        return response_error('No assets state for this case.')


@case_assets_blueprint.route('/case/assets/autoload', methods=['POST'])
@api_login_required
def autoload_asset(caseid):
    """
    Read the investigations database of the current user's case and extract the
    available assets. For each assets, 
    :return:
    """

    return response_error("Will only be available in the future")


@case_assets_blueprint.route('/case/assets/add/modal', methods=['GET'])
@login_required
def add_asset_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_assets.case_assets', cid=caseid))

    form = AssetBasicForm()

    form.asset_type_id.choices = get_assets_types()
    form.analysis_status_id.choices = get_analysis_status_list()

    # Get IoCs from the case
    ioc = get_iocs(caseid)

    return render_template("modal_add_case_asset.html", form=form, asset=None, ioc=ioc)


@case_assets_blueprint.route('/case/assets/add', methods=['POST'])
@api_login_required
def add_asset(caseid):

    try:
        # validate before saving
        add_asset_schema = CaseAssetsSchema()
        jsdata = request.get_json()
        asset = add_asset_schema.load(jsdata)

        asset = create_asset(asset=asset,
                             caseid=caseid,
                             user_id=current_user.id
                             )

        if jsdata.get('ioc_links'):
            set_ioc_links(jsdata.get('ioc_links'), asset.asset_id)

        if asset:
            track_activity("added asset {}".format(asset.asset_name), caseid=caseid)
            return response_success(data=add_asset_schema.dump(asset))

        return response_error("Unable to create asset for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@case_assets_blueprint.route('/case/assets/<int:cur_id>', methods=['GET'])
@api_login_required
def asset_view(cur_id, caseid):

    # Get IoCs already linked to the asset
    asset_iocs = get_linked_iocs_finfo_from_asset(cur_id)

    ioc_prefill = [row._asdict() for row in asset_iocs]

    asset = get_asset(cur_id, caseid)
    if not asset:
        return response_error("Invalid asset ID for this case")

    asset_schema = CaseAssetsSchema()
    data = asset_schema.dump(asset)
    data['linked_ioc'] = ioc_prefill

    return response_success(data=data)


@case_assets_blueprint.route('/case/assets/<int:cur_id>/modal', methods=['GET'])
@login_required
def asset_view_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_assets.case_assets', cid=caseid))

    # Get IoCs from the case
    case_iocs = get_iocs(caseid)

    # Get IoCs already linked to the asset
    asset_iocs = get_linked_iocs_id_from_asset(cur_id)

    ioc_prefill = [row for row in asset_iocs]

    # Build the form
    form = AssetBasicForm()
    asset = get_asset(cur_id, caseid)

    form.asset_name.render_kw = {'value': asset.asset_name}
    form.asset_description.data = asset.asset_description
    form.asset_info.data = asset.asset_info
    form.asset_ip.render_kw = {'value': asset.asset_ip}
    form.asset_domain.render_kw = {'value': asset.asset_domain}
    form.asset_compromised.data = True if asset.asset_compromised else False
    form.asset_type_id.choices = get_assets_types()
    form.analysis_status_id.choices = get_analysis_status_list()

    return render_template("modal_add_case_asset.html", form=form, asset=asset, map={}, ioc=case_iocs,
                           ioc_prefill=ioc_prefill)


@case_assets_blueprint.route('/case/assets/update/<int:cur_id>', methods=['POST'])
@api_login_required
def asset_update(cur_id, caseid):

    try:
        asset = get_asset(cur_id, caseid)
        if not asset:
            return response_error("Invalid asset ID for this case")

        # validate before saving
        add_asset_schema = CaseAssetsSchema()
        asset_schema = add_asset_schema.load(request.get_json(), instance=asset)

        update_assets_state(caseid=caseid)
        db.session.commit()

        if hasattr(asset_schema, 'ioc_links'):
            set_ioc_links(asset_schema.ioc_links, asset.asset_id)

        if asset:
            track_activity("updated asset {}".format(asset.asset_name), caseid=caseid)
            return response_success("Updated asset {}".format(asset.asset_name))

        return response_error("Unable to update asset for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@case_assets_blueprint.route('/case/assets/delete/<int:cur_id>', methods=['GET'])
@api_login_required
def asset_delete(cur_id, caseid):

    asset = get_asset(cur_id, caseid)
    if not asset:
        return response_error("Invalid asset ID for this case")

    # Deletes an asset and the potential links with the IoCs from the database
    delete_asset(cur_id, caseid)

    track_activity("removed asset ID {}".format(cur_id), caseid=caseid)

    return response_success("Deleted")
