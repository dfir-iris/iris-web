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

import csv
from datetime import datetime
import marshmallow
from flask import Blueprint
from flask import request
from flask_login import current_user

from app import db
from app.blueprints.rest.case_comments import case_comment_update
from app.blueprints.rest.endpoints import endpoint_deprecated
from app.business.assets import assets_delete
from app.business.assets import assets_create
from app.business.assets import assets_get_detailed
from app.business.assets import assets_get
from app.business.errors import BusinessProcessingError
from app.datamgmt.case.case_assets_db import case_assets_db_exists, get_raw_assets
from app.datamgmt.case.case_assets_db import add_comment_to_asset
from app.datamgmt.case.case_assets_db import create_asset
from app.datamgmt.case.case_assets_db import delete_asset_comment
from app.datamgmt.case.case_assets_db import get_asset
from app.datamgmt.case.case_assets_db import get_asset_type_id
from app.datamgmt.case.case_assets_db import get_assets
from app.datamgmt.case.case_assets_db import get_assets_ioc_links
from app.datamgmt.case.case_assets_db import get_case_asset_comment
from app.datamgmt.case.case_assets_db import get_case_asset_comments
from app.datamgmt.case.case_assets_db import get_similar_assets
from app.datamgmt.case.case_assets_db import set_ioc_links
from app.datamgmt.case.case_db import get_case_client_id
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.manage.manage_users_db import get_user_cases_fast
from app.datamgmt.states import get_assets_state
from app.datamgmt.states import update_assets_state
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.models import AnalysisStatus
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import CaseAssetsSchema
from app.schema.marshables import CommentSchema
from app.blueprints.access_controls import ac_requires_case_identifier
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success
from app.blueprints.access_controls import ac_api_return_access_denied

case_assets_rest_blueprint = Blueprint('case_assets_rest', __name__)


@case_assets_rest_blueprint.route('/case/assets/filter', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_filter_assets(caseid):
    """
    Returns the list of assets from the case.
    :return: A JSON object containing the assets of the case, enhanced with assets seen on other cases.
    """

    # Get all assets objects from the case and the customer id
    ret = {}
    assets = CaseAssetsSchema().dump(get_raw_assets(caseid), many=True)
    customer_id = get_case_client_id(caseid)

    ioc_links_req = get_assets_ioc_links(caseid)

    cache_ioc_link = {}
    for ioc in ioc_links_req:

        if ioc.asset_id not in cache_ioc_link:
            cache_ioc_link[ioc.asset_id] = [ioc._asdict()]
        else:
            cache_ioc_link[ioc.asset_id].append(ioc._asdict())

    cases_access = get_user_cases_fast(current_user.id)

    for a in assets:
        a['ioc_links'] = cache_ioc_link.get(a['asset_id'])

        if len(assets) < 300:
            # Find similar assets from other cases with the same customer
            a['link'] = list(get_similar_assets(
                a['asset_name'], a['asset_type_id'], caseid, customer_id, cases_access))
        else:
            a['link'] = []

    ret['assets'] = assets

    ret['state'] = get_assets_state(caseid=caseid)

    return response_success("", data=ret)

@case_assets_rest_blueprint.route('/case/assets/list', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_list_assets(caseid):
    """
    Returns the list of assets from the case.
    :return: A JSON object containing the assets of the case, enhanced with assets seen on other cases.
    """
    # Get all assets objects from the case and the customer id
    assets = get_assets(caseid)
    customer_id = get_case_client_id(caseid)

    ret = {'assets': []}

    ioc_links_req = get_assets_ioc_links(caseid)

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
                asset['asset_name'], asset['asset_type_id'], caseid, customer_id, cases_access))
        else:
            asset['link'] = []

        asset['ioc_links'] = cache_ioc_link.get(asset['asset_id'])

        ret['assets'].append(asset)

    ret['state'] = get_assets_state(caseid=caseid)

    return response_success("", data=ret)


@case_assets_rest_blueprint.route('/case/assets/state', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_assets_state(caseid):
    os = get_assets_state(caseid=caseid)
    if os:
        return response_success(data=os)
    return response_error('No assets state for this case.')


@case_assets_rest_blueprint.route('/case/assets/add', methods=['POST'])
@endpoint_deprecated('POST', '/api/v2/cases/<int:caseid>/assets')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def deprecated_add_asset(caseid):
    asset_schema = CaseAssetsSchema()
    try:
        asset, msg = assets_create(caseid, request.get_json())
        return response_success(msg, asset_schema.dump(asset))
    except BusinessProcessingError as e:
        return response_error(e.get_message())


@case_assets_rest_blueprint.route('/case/assets/upload', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_upload_ioc(caseid):
    try:
        # validate before saving
        add_asset_schema = CaseAssetsSchema()
        jsdata = request.get_json()

        # get IOC list from request
        csv_lines = jsdata["CSVData"].splitlines()  # unavoidable since the file is passed as a string

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
                track_activity("Attempted to upload an empty asset name")
                index += 1
                continue

            if row.get("asset_tags"):
                row["asset_tags"] = row.get("asset_tags").replace("|", ",")  # Reformat Tags

            if not row.get('asset_type_name'):
                errors.append(f"Empty asset type for row {index}")
                track_activity("Attempted to upload an empty asset type")
                index += 1
                continue

            type_id = get_asset_type_id(row['asset_type_name'].lower())
            if not type_id:
                errors.append(f"{row.get('asset_name')} (invalid asset type: {row.get('asset_type_name')}) for row {index}")
                track_activity(f"Attempted to upload unrecognized asset type \"{row.get('asset_type_name')}\"")
                index += 1
                continue

            row['asset_type_id'] = type_id.asset_id
            row.pop('asset_type_name', None)

            row['analysis_status_id'] = analysis_status_id

            request_data = call_modules_hook('on_preload_asset_create', data=row, caseid=caseid)

            add_asset_schema.is_unique_for_cid(caseid, request_data)
            asset_sc = add_asset_schema.load(request_data)
            asset_sc.custom_attributes = get_default_custom_attributes('asset')
            asset = create_asset(asset=asset_sc,
                                 caseid=caseid,
                                 user_id=current_user.id
                                 )

            asset = call_modules_hook('on_postload_asset_create', data=asset, caseid=caseid)

            if not asset:
                errors.append('Unable to add asset for internal reason')
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
        return response_error(msg='Data error', data=e.messages)


@case_assets_rest_blueprint.route('/case/assets/<int:cur_id>', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/cases/<int:case_identifier>/assets/<int:cur_id>')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def deprecated_asset_view(cur_id, caseid):
    try:
        asset = assets_get_detailed(cur_id)
        return response_success(asset)
    except BusinessProcessingError as e:
        return response_error(e.get_message())


@case_assets_rest_blueprint.route('/case/assets/update/<int:cur_id>', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def asset_update(cur_id, caseid):
    try:
        asset = get_asset(cur_id)
        if not asset:
            return response_error("Invalid asset ID for this case")

        # validate before saving
        add_asset_schema = CaseAssetsSchema()

        request_data = call_modules_hook('on_preload_asset_update', data=request.get_json(), caseid=caseid)

        request_data['asset_id'] = cur_id

        asset_schema = add_asset_schema.load(request_data, instance=asset)
        asset_schema.case_id = caseid
        if case_assets_db_exists(asset_schema):
            return response_error('Data error', data='Asset with same value and type already exists')

        update_assets_state(caseid=caseid)
        db.session.commit()

        if hasattr(asset_schema, 'ioc_links'):
            errors, _ = set_ioc_links(asset_schema.ioc_links, asset.asset_id)
            if errors:
                return response_error('Encountered errors while linking IOC. Asset has still been updated.')

        asset_schema = call_modules_hook('on_postload_asset_update', data=asset_schema, caseid=caseid)

        if asset_schema:
            track_activity(f"updated asset \"{asset_schema.asset_name}\"", caseid=caseid)
            return response_success("Updated asset {}".format(asset_schema.asset_name),
                                    add_asset_schema.dump(asset_schema))

        return response_error("Unable to update asset for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg='Data error', data=e.messages)


@case_assets_rest_blueprint.route('/case/assets/delete/<int:cur_id>', methods=['POST'])
@endpoint_deprecated('DELETE', '/api/v2/cases/<case_identifier>/assets/<int:cur_id>')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def deprecated_asset_delete(cur_id, caseid):
    try:
        asset = assets_get(cur_id)
        if not ac_fast_check_current_user_has_case_access(asset.case_id, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=asset.case_id)

        assets_delete(asset)
        return response_success('Deleted')
    except BusinessProcessingError as _:
        return response_error('Invalid asset ID for this case')


@case_assets_rest_blueprint.route('/case/assets/<int:cur_id>/comments/list', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_asset_list(cur_id, caseid):
    asset_comments = get_case_asset_comments(cur_id)
    if asset_comments is None:
        return response_error('Invalid asset ID')

    return response_success(data=CommentSchema(many=True).dump(asset_comments))


@case_assets_rest_blueprint.route('/case/assets/<int:cur_id>/comments/add', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_asset_add(cur_id, caseid):
    try:
        asset = get_asset(cur_id)
        if not asset:
            return response_error('Invalid asset ID')

        comment_schema = CommentSchema()

        comment = comment_schema.load(request.get_json())
        comment.comment_case_id = caseid
        comment.comment_user_id = current_user.id
        comment.comment_date = datetime.now()
        comment.comment_update_date = datetime.now()
        db.session.add(comment)
        db.session.commit()

        add_comment_to_asset(asset.asset_id, comment.comment_id)

        db.session.commit()

        hook_data = {
            "comment": comment_schema.dump(comment),
            "asset": CaseAssetsSchema().dump(asset)
        }
        call_modules_hook('on_postload_asset_commented', data=hook_data, caseid=caseid)

        track_activity(f"asset \"{asset.asset_name}\" commented", caseid=caseid)
        return response_success("Asset commented", data=comment_schema.dump(comment))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages())


@case_assets_rest_blueprint.route('/case/assets/<int:cur_id>/comments/<int:com_id>', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_asset_get(cur_id, com_id, caseid):
    comment = get_case_asset_comment(cur_id, com_id)
    if not comment:
        return response_error("Invalid comment ID")

    return response_success(data=comment._asdict())


@case_assets_rest_blueprint.route('/case/assets/<int:cur_id>/comments/<int:com_id>/edit', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_asset_edit(cur_id, com_id, caseid):
    return case_comment_update(com_id, 'assets', caseid)


@case_assets_rest_blueprint.route('/case/assets/<int:cur_id>/comments/<int:com_id>/delete', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_asset_delete(cur_id, com_id, caseid):
    success, msg = delete_asset_comment(cur_id, com_id, caseid)
    if not success:
        return response_error(msg)

    call_modules_hook('on_postload_asset_comment_delete', data=com_id, caseid=caseid)

    track_activity(f"comment {com_id} on asset {cur_id} deleted", caseid=caseid)
    return response_success(msg)