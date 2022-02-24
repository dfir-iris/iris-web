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
import logging as log

import marshmallow
from flask import Blueprint, request
from flask import render_template, url_for, redirect
from flask_login import current_user

from app import db
from app.configuration import misp_url
from app.datamgmt.case.case_assets_db import get_assets_types
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_iocs_db import get_detailed_iocs, get_ioc_links, add_ioc, add_ioc_link, \
    get_tlps, get_ioc, delete_ioc, get_ioc_types_list, check_ioc_type_id, get_tlps_dict, get_ioc_type_id
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import get_ioc_state, update_ioc_state
from app.forms import ModalAddCaseAssetForm, ModalAddCaseIOCForm
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.models import Ioc
from app.schema.marshables import IocSchema
from app.util import response_success, response_error, login_required, api_login_required

case_ioc_blueprint = Blueprint(
    'case_ioc',
    __name__,
    template_folder='templates'
)


# CONTENT ------------------------------------------------
@case_ioc_blueprint.route('/case/ioc', methods=['GET', 'POST'])
@login_required
def case_ioc(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_ioc.case_ioc', cid=caseid, redirect=True))

    form = ModalAddCaseAssetForm()
    form.asset_id.choices = get_assets_types()

    # Retrieve the assets linked to the investigation
    case = get_case(caseid)

    return render_template("case_ioc.html", case=case, form=form)


@case_ioc_blueprint.route('/case/ioc/list', methods=['GET'])
@api_login_required
def case_list_ioc(caseid):
    iocs = get_detailed_iocs(caseid)

    ret = {}
    ret['ioc'] = []

    for ioc in iocs:
        out = ioc._asdict()

        # Get links of the IoCs seen in other cases
        ial = get_ioc_links(ioc.ioc_id, caseid)

        out['link'] = [row._asdict() for row in ial]
        out['misp_link'] = misp_url

        ret['ioc'].append(out)

    ret['state'] = get_ioc_state(caseid=caseid)

    return response_success("", data=ret)


@case_ioc_blueprint.route('/case/ioc/state', methods=['GET'])
@api_login_required
def case_ioc_state(caseid):
    os = get_ioc_state(caseid=caseid)
    if os:
        return response_success(data=os)
    else:
        return response_error('No IOC state for this case.')


@case_ioc_blueprint.route('/case/ioc/add', methods=['POST'])
@api_login_required
def case_add_ioc(caseid):
    try:
        # validate before saving
        add_ioc_schema = IocSchema()

        request_data = call_modules_hook('on_preload_ioc_create', data=request.get_json(), caseid=caseid)

        ioc = add_ioc_schema.load(request_data)

        if not check_ioc_type_id(type_id=ioc.ioc_type_id):
            return response_error("Not a valid IOC type")

        ioc, existed = add_ioc(ioc=ioc,
                               user_id=current_user.id,
                               caseid=caseid
                               )
        link_existed = add_ioc_link(ioc.ioc_id, caseid)

        if link_existed:
            return response_error("IOC already exists and linked to this case", data=add_ioc_schema.dump(ioc))

        if not link_existed:
            ioc = call_modules_hook('on_postload_ioc_create', data=ioc, caseid=caseid)

        if ioc:
            track_activity("added ioc {} via file upload".format(ioc.ioc_value), caseid=caseid)

            msg = "IOC already existed in DB. Updated with info on DB." if existed else "IOC added"

            return response_success(msg=msg, data=add_ioc_schema.dump(ioc))

        return response_error("Unable to create IOC for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@case_ioc_blueprint.route('/case/ioc/upload', methods=['POST'])
@api_login_required
def case_upload_ioc(caseid):
    try:
        # validate before saving
        add_ioc_schema = IocSchema()
        jsdata = request.get_json()

        # get IOC list from request
        headers = "ioc_value,ioc_type,ioc_description,ioc_tags,ioc_tlp"
        csv_lines = jsdata["CSVData"].splitlines()  # unavoidable since the file is passed as a string
        if csv_lines[0].lower() != headers:
            csv_lines.insert(0, headers)

        # convert list of strings into CSV
        csv_data = csv.DictReader(csv_lines, quotechar='"', delimiter=',')

        # build a Dict of possible TLP
        tlp_dict = get_tlps_dict()
        ret = []
        errors = []

        index = 0
        for row in csv_data:

            for e in headers.split(','):
                if row.get(e) is None:
                    errors.append(f"{e} is missing for row {index}")
                    index += 1
                    continue

            # IOC value must not be empty
            if not row.get("ioc_value"):
                errors.append(f"Empty IOC value for row {index}")
                track_activity(f"Attempted to upload an empty IOC value")
                index += 1
                continue

            row["ioc_tags"] = row["ioc_tags"].replace("|", ",")  # Reformat Tags

            # Convert TLP into TLP id
            if row["ioc_tlp"] in tlp_dict:
                row["ioc_tlp_id"] = tlp_dict[row["ioc_tlp"]]
            else:
                row["ioc_tlp_id"] = ""
            row.pop("ioc_tlp", None)

            type_id = get_ioc_type_id(row['ioc_type'].lower())
            if not type_id:
                errors.append(f"{row['ioc_value']} (invalid ioc type: {row['ioc_type']}) for row {index}")
                log.error(f'Unrecognised IOC type {row["ioc_type"]}')
                index += 1
                continue

            row['ioc_type_id'] = type_id.type_id
            row.pop('ioc_type', None)

            request_data = call_modules_hook('on_preload_ioc_create', data=row, caseid=caseid)

            ioc = add_ioc_schema.load(request_data)
            ioc.custom_attributes = get_default_custom_attributes('ioc')
            ioc, existed = add_ioc(ioc=ioc,
                                   user_id=current_user.id,
                                   caseid=caseid
                                   )
            link_existed = add_ioc_link(ioc.ioc_id, caseid)

            if link_existed:
                errors.append(f"{ioc.ioc_value} (already exists and linked to this case)")
                log.error(f"IOC {ioc.ioc_value} already exists and linked to this case")
                index += 1
                continue

            if ioc:
                ioc = call_modules_hook('on_postload_ioc_create', data=ioc, caseid=caseid)
                ret.append(request_data)
                track_activity(f"added ioc {ioc.ioc_value}", caseid=caseid)

            else:
                errors.append(f"{ioc.ioc_value} (internal reasons)")
                log.error(f"Unable to create IOC {ioc.ioc_value} for internal reasons")

            index += 1

        if len(errors) == 0:
            msg = "Successfully imported data."
        else:
            msg = "Data is imported but we got errors with the following rows:\n- " + "\n- ".join(errors)

        return response_success(msg=msg, data=ret)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@case_ioc_blueprint.route('/case/ioc/add/modal', methods=['GET'])
@login_required
def case_add_ioc_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_ioc.case_ioc', cid=caseid, redirect=True))

    form = ModalAddCaseIOCForm()
    form.ioc_type_id.choices = [(row['type_id'], row['type_name']) for row in get_ioc_types_list()]
    form.ioc_tlp_id.choices = get_tlps()

    attributes = get_default_custom_attributes('ioc')

    return render_template("modal_add_case_ioc.html", form=form, ioc=Ioc(), attributes=attributes)


@case_ioc_blueprint.route('/case/ioc/delete/<int:cur_id>', methods=['GET'])
@api_login_required
def case_delete_ioc(cur_id, caseid):
    call_modules_hook('on_preload_ioc_delete', data=cur_id, caseid=caseid)
    ioc = get_ioc(cur_id, caseid)

    if not ioc:
        return response_error('Not a valid IOC for this case')

    if not delete_ioc(ioc, caseid):
        track_activity("unlinked IOC ID {}".format(cur_id))
        return response_success("IOC unlinked")

    call_modules_hook('on_postload_ioc_delete', data=cur_id, caseid=caseid)

    track_activity("deleted IOC ID {}".format(cur_id))
    return response_success("IOC deleted")


@case_ioc_blueprint.route('/case/ioc/<int:cur_id>/modal', methods=['GET'])
@login_required
def case_view_ioc_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_assets.case_assets', cid=caseid, redirect=True))

    form = ModalAddCaseIOCForm()
    ioc = get_ioc(cur_id, caseid)
    if not ioc:
        return response_error("Invalid IOC ID for this case")

    form.ioc_type_id.choices = [(row['type_id'], row['type_name']) for row in get_ioc_types_list()]
    form.ioc_tlp_id.choices = get_tlps()

    # Render the IOC
    form.ioc_tags.render_kw = {'value': ioc.ioc_tags}
    form.ioc_description.data = ioc.ioc_description
    form.ioc_value.data = ioc.ioc_value

    return render_template("modal_add_case_ioc.html", form=form, ioc=ioc, attributes=ioc.custom_attributes)


@case_ioc_blueprint.route('/case/ioc/<int:cur_id>', methods=['GET'])
@api_login_required
def case_view_ioc(cur_id, caseid):
    ioc_schema = IocSchema()
    ioc = get_ioc(cur_id, caseid)
    if not ioc:
        return response_error("Invalid IOC ID for this case")

    return response_success(data=ioc_schema.dump(ioc))


@case_ioc_blueprint.route('/case/ioc/update/<int:cur_id>', methods=['POST'])
@api_login_required
def case_update_ioc(cur_id, caseid):
    try:
        ioc = get_ioc(cur_id, caseid)
        if not ioc:
            return response_error("Invalid IOC ID for this case")

        request_data = call_modules_hook('on_preload_ioc_update', data=request.get_json(), caseid=caseid)

        # validate before saving
        ioc_schema = IocSchema()
        request_data['ioc_id'] = cur_id
        ioc_sc = ioc_schema.load(request_data, instance=ioc)
        ioc_sc.user_id = current_user.id

        if not check_ioc_type_id(type_id=ioc_sc.ioc_type_id):
            return response_error("Not a valid IOC type")

        update_ioc_state(caseid=caseid)
        db.session.commit()

        ioc_sc = call_modules_hook('on_postload_ioc_update', data=ioc_sc, caseid=caseid)

        if ioc_sc:
            track_activity("updated ioc {}".format(ioc_sc.ioc_value), caseid=caseid)
            return response_success("Updated ioc {}".format(ioc_sc.ioc_value), data=ioc_schema.dump(ioc))

        return response_error("Unable to update ioc for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)
