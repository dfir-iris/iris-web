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
import json
from flask import Blueprint
from flask import render_template, request, url_for, redirect

from app import db
from app.datamgmt.manage.manage_attribute_db import update_all_attributes
from app.forms import AddAssetForm, AttributeForm
from app.models.models import CustomAttribute
from app.util import response_success, response_error, admin_required, api_admin_required, \
    api_login_required

manage_attributes_blueprint = Blueprint('manage_attributes',
                                          __name__,
                                          template_folder='templates')


# CONTENT ------------------------------------------------
@manage_attributes_blueprint.route('/manage/attributes')
@admin_required
def manage_attributes(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_attributes.manage_attributes', cid=caseid))

    form = AddAssetForm()

    return render_template('manage_attributes.html', form=form)


@manage_attributes_blueprint.route('/manage/attributes/list')
@api_login_required
def list_attributes(caseid):
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
@admin_required
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
@admin_required
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
@api_admin_required
def update_attribute(cur_id, caseid):
    if not request.is_json:
        return response_error("Invalid request")

    attribute = CustomAttribute.query.filter(CustomAttribute.attribute_id == cur_id).first()
    if not attribute:
        return response_error(f"Invalid Attribute ID {cur_id}")

    data = request.get_json()
    attr_content = data.get('attribute_content')
    if not attr_content:
        return response_error("Invalid request")

    attribute.attribute_content = dict(json.loads(attr_content))
    db.session.commit()

    # Now try to update every attributes by merging the updated ones
    update_all_attributes(attribute.attribute_for)

    return response_success("Attribute updated")