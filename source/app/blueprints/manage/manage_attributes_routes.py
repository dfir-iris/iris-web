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

import json
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from app import db
from app.datamgmt.manage.manage_attribute_db import update_all_attributes
from app.datamgmt.manage.manage_attribute_db import validate_attribute
from app.forms import AddAssetForm
from app.forms import AttributeForm
from app.models.authorization import Permissions
from app.models.models import CustomAttribute
from app.util import ac_api_requires
from app.util import ac_requires
from app.util import response_error
from app.util import response_success

manage_attributes_blueprint = Blueprint('manage_attributes', __name__, template_folder='templates')


# CONTENT ------------------------------------------------
@manage_attributes_blueprint.route('/manage/attributes')
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_attributes(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_attributes.manage_attributes', cid=caseid))

    form = AddAssetForm()

    return render_template('manage_attributes.html', form=form)


@manage_attributes_blueprint.route('/manage/attributes/list')
@ac_api_requires(Permissions.server_administrator)
def list_attributes():
    # Get all attributes
    attributes = CustomAttribute.query.with_entities(
        CustomAttribute.attribute_id,
        CustomAttribute.attribute_content,
        CustomAttribute.attribute_display_name,
        CustomAttribute.attribute_description,
        CustomAttribute.attribute_for
    ).all()

    data = [row._asdict() for row in attributes]

    # Return the attributes
    return response_success("", data=data)


@manage_attributes_blueprint.route('/manage/attributes/<int:cur_id>/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def attributes_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_attributes.manage_attributes', cid=caseid))

    form = AttributeForm()

    attribute = CustomAttribute.query.filter(CustomAttribute.attribute_id == cur_id).first()
    if not attribute:
        return response_error(f"Invalid Attribute ID {cur_id}")

    form.attribute_content.data = attribute.attribute_content

    return render_template("modal_add_attribute.html", form=form, attribute=attribute)


@manage_attributes_blueprint.route('/manage/attributes/preview', methods=['POST'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def attributes_preview(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_attributes.manage_attributes', cid=caseid))

    data = request.get_json()
    if not data:
        return response_error(f"Invalid request")

    attribute = data.get('attribute_content')
    if not attribute:
        return response_error(f"Invalid request")

    try:
        attribute = json.loads(attribute)
    except Exception as e:
        return response_error("Invalid JSON", data=str(e))

    templated = render_template("modal_preview_attribute.html", attributes=attribute)

    return response_success(data=templated)


@manage_attributes_blueprint.route('/manage/attributes/update/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def update_attribute(cur_id):
    if not request.is_json:
        return response_error("Invalid request")

    attribute = CustomAttribute.query.filter(CustomAttribute.attribute_id == cur_id).first()
    if not attribute:
        return response_error(f"Invalid Attribute ID {cur_id}")

    data = request.get_json()
    attr_content = data.get('attribute_content')
    if not attr_content:
        return response_error("Invalid request")

    attr_contents, logs = validate_attribute(attr_content)
    if len(logs) > 0:
        return response_error("Found errors in attribute", data=logs)

    previous_attribute = attribute.attribute_content

    attribute.attribute_content = attr_contents
    db.session.commit()

    # Now try to update every attributes by merging the updated ones
    complete_overwrite = data.get('complete_overwrite')
    complete_overwrite = complete_overwrite if complete_overwrite else False
    partial_overwrite = data.get('partial_overwrite')
    partial_overwrite = partial_overwrite if partial_overwrite else False
    update_all_attributes(attribute.attribute_for, partial_overwrite=partial_overwrite,
                          complete_overwrite=complete_overwrite, previous_attribute=previous_attribute)

    return response_success("Attribute updated")
