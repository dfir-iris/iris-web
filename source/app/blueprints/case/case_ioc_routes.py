#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS) - DFIR-IRIS Team
#  ir@cyberactionlab.net - contact@dfir-iris.org
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
from datetime import datetime

import csv
import logging as log
import marshmallow
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user

from app import db
from app.blueprints.case.case_comments import case_comment_update
from app.datamgmt.case.case_assets_db import get_assets_types
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_iocs_db import add_comment_to_ioc
from app.datamgmt.case.case_iocs_db import add_ioc
from app.datamgmt.case.case_iocs_db import add_ioc_link
from app.datamgmt.case.case_iocs_db import delete_ioc_comment
from app.datamgmt.case.case_iocs_db import get_case_ioc_comment
from app.datamgmt.case.case_iocs_db import get_case_ioc_comments
from app.datamgmt.case.case_iocs_db import get_case_iocs_comments_count
from app.datamgmt.case.case_iocs_db import get_detailed_iocs
from app.datamgmt.case.case_iocs_db import get_ioc
from app.datamgmt.case.case_iocs_db import get_ioc_links
from app.datamgmt.case.case_iocs_db import get_ioc_type_id
from app.datamgmt.case.case_iocs_db import get_ioc_types_list
from app.datamgmt.case.case_iocs_db import get_tlps
from app.datamgmt.case.case_iocs_db import get_tlps_dict
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import get_ioc_state
from app.forms import ModalAddCaseAssetForm
from app.forms import ModalAddCaseIOCForm
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.models.models import Ioc
from app.schema.marshables import CommentSchema
from app.schema.marshables import IocSchema
from app.util import ac_api_case_requires
from app.util import ac_case_requires
from app.util import response_error
from app.util import response_success
from app.business.iocs import create
from app.business.iocs import update
from app.business.iocs import delete
from app.business.errors import BusinessProcessingError

case_ioc_blueprint = Blueprint(
    'case_ioc',
    __name__,
    template_folder='templates'
)


# CONTENT ------------------------------------------------
@case_ioc_blueprint.route('/case/ioc', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_ioc(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_ioc.case_ioc', cid=caseid, redirect=True))

    form = ModalAddCaseAssetForm()
    form.asset_id.choices = get_assets_types()

    # Retrieve the assets linked to the investigation
    case = get_case(caseid)

    return render_template("case_ioc.html", case=case, form=form)


@case_ioc_blueprint.route('/case/ioc/list', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_list_ioc(caseid):
    iocs = get_detailed_iocs(caseid)

    ret = {}
    ret['ioc'] = []

    for ioc in iocs:
        out = ioc._asdict()

        # Get links of the IoCs seen in other cases
        ial = get_ioc_links(ioc.ioc_id, caseid)

        out['link'] = [row._asdict() for row in ial]
        # Legacy, must be changed next version
        out['misp_link'] = None

        ret['ioc'].append(out)

    ret['state'] = get_ioc_state(caseid=caseid)

    return response_success("", data=ret)


@case_ioc_blueprint.route('/case/ioc/state', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_ioc_state(caseid):
    os = get_ioc_state(caseid=caseid)
    if os:
        return response_success(data=os)
    else:
        return response_error('No IOC state for this case.')


@case_ioc_blueprint.route('/case/ioc/add', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_add_ioc(caseid):
    ioc_schema = IocSchema()

    try:
        ioc, msg = create(request.get_json(), caseid)
        return response_success(msg, data=ioc_schema.dump(ioc))
    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@case_ioc_blueprint.route('/case/ioc/upload', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
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
                track_activity(f"added ioc \"{ioc.ioc_value}\"", caseid=caseid)

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
        return response_error(msg="Data error", data=e.messages)


@case_ioc_blueprint.route('/case/ioc/add/modal', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_add_ioc_modal(caseid):

    form = ModalAddCaseIOCForm()
    form.ioc_type_id.choices = [(row['type_id'], row['type_name']) for row in get_ioc_types_list()]
    form.ioc_tlp_id.choices = get_tlps()

    attributes = get_default_custom_attributes('ioc')

    return render_template("modal_add_case_ioc.html", form=form, ioc=Ioc(), attributes=attributes)


@case_ioc_blueprint.route('/case/ioc/delete/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_delete_ioc(cur_id, caseid):
    try:

        msg = delete(cur_id, caseid)
        return response_success(msg=msg)

    except BusinessProcessingError as e:
        return response_error(e.get_message())


@case_ioc_blueprint.route('/case/ioc/<int:cur_id>/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
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
    comments_map = get_case_iocs_comments_count([cur_id])

    return render_template("modal_add_case_ioc.html", form=form, ioc=ioc, attributes=ioc.custom_attributes,
                           comments_map=comments_map)


@case_ioc_blueprint.route('/case/ioc/<int:cur_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_view_ioc(cur_id, caseid):
    ioc_schema = IocSchema()
    ioc = get_ioc(cur_id, caseid)
    if not ioc:
        return response_error("Invalid IOC ID for this case")

    return response_success(data=ioc_schema.dump(ioc))


@case_ioc_blueprint.route('/case/ioc/update/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_update_ioc(cur_id, caseid):
    ioc_schema = IocSchema()

    try:
        ioc, msg = update(cur_id, request.get_json(), caseid)
        return response_success(msg, data=ioc_schema.dump(ioc))
    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@case_ioc_blueprint.route('/case/ioc/<int:cur_id>/comments/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_ioc_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_ioc.case_ioc', cid=caseid, redirect=True))

    ioc = get_ioc(cur_id, caseid=caseid)
    if not ioc:
        return response_error('Invalid ioc ID')

    return render_template("modal_conversation.html", element_id=cur_id, element_type='ioc',
                           title=ioc.ioc_value)


@case_ioc_blueprint.route('/case/ioc/<int:cur_id>/comments/list', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_ioc_list(cur_id, caseid):

    ioc_comments = get_case_ioc_comments(cur_id)
    if ioc_comments is None:
        return response_error('Invalid ioc ID')

    return response_success(data=CommentSchema(many=True).dump(ioc_comments))


@case_ioc_blueprint.route('/case/ioc/<int:cur_id>/comments/add', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_ioc_add(cur_id, caseid):

    try:
        ioc = get_ioc(cur_id, caseid=caseid)
        if not ioc:
            return response_error('Invalid ioc ID')

        comment_schema = CommentSchema()

        comment = comment_schema.load(request.get_json())
        comment.comment_case_id = caseid
        comment.comment_user_id = current_user.id
        comment.comment_date = datetime.now()
        comment.comment_update_date = datetime.now()
        db.session.add(comment)
        db.session.commit()

        add_comment_to_ioc(ioc.ioc_id, comment.comment_id)

        db.session.commit()

        hook_data = {
            "comment": comment_schema.dump(comment),
            "ioc": IocSchema().dump(ioc)
        }
        call_modules_hook('on_postload_ioc_commented', data=hook_data, caseid=caseid)

        track_activity(f"ioc \"{ioc.ioc_value}\" commented", caseid=caseid)
        return response_success("Event commented", data=comment_schema.dump(comment))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages())


@case_ioc_blueprint.route('/case/ioc/<int:cur_id>/comments/<int:com_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_ioc_get(cur_id, com_id, caseid):

    comment = get_case_ioc_comment(cur_id, com_id)
    if not comment:
        return response_error("Invalid comment ID")

    return response_success(data=comment._asdict())


@case_ioc_blueprint.route('/case/ioc/<int:cur_id>/comments/<int:com_id>/edit', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_ioc_edit(cur_id, com_id, caseid):

    return case_comment_update(com_id, 'ioc', caseid)


@case_ioc_blueprint.route('/case/ioc/<int:cur_id>/comments/<int:com_id>/delete', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_ioc_delete(cur_id, com_id, caseid):

    success, msg = delete_ioc_comment(cur_id, com_id)
    if not success:
        return response_error(msg)

    call_modules_hook('on_postload_ioc_comment_delete', data=com_id, caseid=caseid)

    track_activity(f"comment {com_id} on ioc {cur_id} deleted", caseid=caseid)
    return response_success(msg)
