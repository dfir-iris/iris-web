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
import csv
import marshmallow
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user

from app import db
from app.datamgmt.case.case_assets_db import create_asset
from app.datamgmt.case.case_assets_db import delete_asset
from app.datamgmt.case.case_assets_db import get_analysis_status_list
from app.datamgmt.case.case_assets_db import get_asset
from app.datamgmt.case.case_assets_db import get_asset_type_id
from app.datamgmt.case.case_assets_db import get_assets
from app.datamgmt.case.case_assets_db import get_assets_types
from app.datamgmt.case.case_assets_db import get_linked_iocs_finfo_from_asset
from app.datamgmt.case.case_assets_db import get_linked_iocs_id_from_asset
from app.datamgmt.case.case_assets_db import get_similar_assets
from app.datamgmt.case.case_assets_db import set_ioc_links
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_db import get_case_client_id
from app.datamgmt.case.case_iocs_db import get_iocs
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import get_assets_state
from app.datamgmt.states import update_assets_state
from app.forms import AssetBasicForm
from app.forms import ModalAddCaseAssetForm
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models import AnalysisStatus
from app.models import Ioc
from app.models import IocAssetLink
from app.models import IocLink
from app.schema.marshables import CaseAssetsSchema
from app.util import api_login_required
from app.util import login_required
from app.util import response_error
from app.util import response_success

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
        return redirect(url_for('case_assets.case_assets', cid=caseid, redirect=True))

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

    ioc_links_req = IocAssetLink.query.with_entities(
        Ioc.ioc_id,
        Ioc.ioc_value,
        IocAssetLink.asset_id
    ).filter(
        Ioc.ioc_id == IocAssetLink.ioc_id,
        IocLink.case_id == caseid,
        IocLink.ioc_id == Ioc.ioc_id
    ).all()

    cache_ioc_link = {}
    for ioc in ioc_links_req:

        if ioc.asset_id not in cache_ioc_link:
            cache_ioc_link[ioc.asset_id] = [ioc._asdict()]
        else:
            cache_ioc_link[ioc.asset_id].append(ioc._asdict())

    for asset in assets:
        asset = asset._asdict()

        # Find linked IoC
        if len(assets) < 300:
            # Find similar assets from other cases with the same customer
            asset['link'] = [lasset._asdict() for lasset in get_similar_assets(
                            asset['asset_name'], asset['asset_type_id'], caseid, customer_id)]
        else:
            asset['link'] = []

        asset['ioc_links'] = cache_ioc_link.get(asset['asset_id'])

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
        return redirect(url_for('case_assets.case_assets', cid=caseid, redirect=True))

    form = AssetBasicForm()

    form.asset_type_id.choices = get_assets_types()
    form.analysis_status_id.choices = get_analysis_status_list()

    # Get IoCs from the case
    ioc = get_iocs(caseid)
    attributes = get_default_custom_attributes('asset')

    return render_template("modal_add_case_asset.html", form=form, asset=None, ioc=ioc, attributes=attributes)


@case_assets_blueprint.route('/case/assets/add', methods=['POST'])
@api_login_required
def add_asset(caseid):

    try:
        # validate before saving
        add_asset_schema = CaseAssetsSchema()
        request_data = call_modules_hook('on_preload_asset_create', data=request.get_json(), caseid=caseid)

        asset = add_asset_schema.load(request_data)

        asset = create_asset(asset=asset,
                             caseid=caseid,
                             user_id=current_user.id
                             )

        if request_data.get('ioc_links'):
            set_ioc_links(request_data.get('ioc_links'), asset.asset_id)

        asset = call_modules_hook('on_postload_asset_create', data=asset, caseid=caseid)

        if asset:
            track_activity("added asset {}".format(asset.asset_name), caseid=caseid)
            return response_success("Asset added", data=add_asset_schema.dump(asset))

        return response_error("Unable to create asset for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@case_assets_blueprint.route('/case/assets/upload', methods=['POST'])
@api_login_required
def case_upload_ioc(caseid):

    try:
        # validate before saving
        add_asset_schema = CaseAssetsSchema()
        jsdata = request.get_json()

        # get IOC list from request
        csv_lines = jsdata["CSVData"].splitlines() # unavoidable since the file is passed as a string

        headers = "asset_name,asset_type_name,asset_description,asset_ip,asset_domain,asset_tags"

        if csv_lines[0].lower() != headers:
            csv_lines.insert(0, headers)

        # convert list of strings into CSV
        csv_data = csv.DictReader(csv_lines, delimiter=',')

        ret = []
        errors = []

        analysis_status = AnalysisStatus.query.filter(AnalysisStatus.name == 'Unspecified').first()
        analysis_status_id = analysis_status.id

        index = 0
        for row in csv_data:
            missing_field = False
            for e in headers.split(','):
                if row.get(e) is None:
                    errors.append(f"{e} is missing for row {index}")
                    missing_field = True
                    continue

            if missing_field:
                continue

            # Asset name must not be empty
            if not row.get("asset_name"):
                errors.append(f"Empty asset name for row {index}")
                track_activity(f"Attempted to upload an empty asset name")
                index += 1
                continue

            if row.get("asset_tags"):
                row["asset_tags"] = row.get("asset_tags").replace("|", ",")  # Reformat Tags

            if not row.get('asset_type_name'):
                errors.append(f"Empty asset type for row {index}")
                track_activity(f"Attempted to upload an empty asset type")
                index += 1
                continue

            type_id = get_asset_type_id(row['asset_type_name'].lower())
            if not type_id:
                errors.append(f"{row.get('asset_name')} (invalid asset type: {row.get('asset_type_name')}) for row {index}")
                track_activity(f"Attempted to upload unrecognized asset type {row.get('asset_type_name')}")
                index += 1
                continue

            row['asset_type_id'] = type_id.asset_id
            row.pop('asset_type_name', None)

            row['analysis_status_id'] = analysis_status_id

            request_data = call_modules_hook('on_preload_asset_create', data=row, caseid=caseid)
            asset_sc = add_asset_schema.load(request_data)
            asset_sc.custom_attributes = get_default_custom_attributes('asset')
            asset = create_asset(asset=asset_sc,
                                 caseid=caseid,
                                 user_id=current_user.id
                                 )

            asset = call_modules_hook('on_postload_asset_create', data=asset, caseid=caseid)

            if not asset:
                errors.append(f"Unable to add asset for internal reason")
                index += 1
                continue

            ret.append(request_data)
            track_activity(f"added asset {asset.asset_name}", caseid=caseid)

            index += 1

        if len(errors) == 0:
            msg = "Successfully imported data."
        else:
            msg = "Data is imported but we got errors with the following rows:\n- " + "\n- ".join(errors)

        return response_success(msg=msg, data=ret)

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
        return redirect(url_for('case_assets.case_assets', cid=caseid, redirect=True))

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
    form.asset_tags.render_kw = {'value': asset.asset_tags}

    return render_template("modal_add_case_asset.html", form=form, asset=asset, map={}, ioc=case_iocs,
                           ioc_prefill=ioc_prefill, attributes=asset.custom_attributes)


@case_assets_blueprint.route('/case/assets/update/<int:cur_id>', methods=['POST'])
@api_login_required
def asset_update(cur_id, caseid):

    try:
        asset = get_asset(cur_id, caseid)
        if not asset:
            return response_error("Invalid asset ID for this case")

        # validate before saving
        add_asset_schema = CaseAssetsSchema()

        request_data = call_modules_hook('on_preload_asset_update', data=request.get_json(), caseid=caseid)

        request_data['asset_id'] = cur_id
        asset_schema = add_asset_schema.load(request_data, instance=asset)

        update_assets_state(caseid=caseid)
        db.session.commit()

        if hasattr(asset_schema, 'ioc_links'):
            set_ioc_links(asset_schema.ioc_links, asset.asset_id)

        asset_schema = call_modules_hook('on_postload_asset_update', data=asset_schema, caseid=caseid)

        if asset_schema:
            track_activity("updated asset {}".format(asset_schema.asset_name), caseid=caseid)
            return response_success("Updated asset {}".format(asset_schema.asset_name), add_asset_schema.dump(asset_schema))

        return response_error("Unable to update asset for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@case_assets_blueprint.route('/case/assets/delete/<int:cur_id>', methods=['GET'])
@api_login_required
def asset_delete(cur_id, caseid):

    call_modules_hook('on_preload_asset_delete', data=cur_id, caseid=caseid)

    asset = get_asset(cur_id, caseid)
    if not asset:
        return response_error("Invalid asset ID for this case")

    # Deletes an asset and the potential links with the IoCs from the database
    delete_asset(cur_id, caseid)

    call_modules_hook('on_postload_asset_delete', data=cur_id, caseid=caseid)

    track_activity("removed asset ID {}".format(cur_id), caseid=caseid)

    return response_success("Deleted")
