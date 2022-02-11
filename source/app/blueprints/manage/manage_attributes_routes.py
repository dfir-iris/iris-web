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

from app.blueprints.manage.manage_assets_type_routes import manage_assets_blueprint
from app.iris_engine.utils.tracker import track_activity
from app.models.models import AssetsType, CaseAssets, CustomAttribute
from app.forms import AddAssetForm, AttributeForm
from app import db

from app.util import response_success, response_error, login_required, admin_required, api_admin_required, \
    api_login_required

manage_attributes_blueprint = Blueprint('manage_attributes',
                                          __name__,
                                          template_folder='templates')


# CONTENT ------------------------------------------------
@manage_attributes_blueprint.route('/manage/attributes')
@admin_required
def manage_attributes(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_attributes_blueprint.manage_attributes', cid=caseid))

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
        return redirect(url_for('manage_attributes_blueprint.manage_attributes', cid=caseid))

    form = AttributeForm()

    attribute = CustomAttribute.query.filter(CustomAttribute.attribute_id == cur_id).first()
    if not attribute:
        return response_error(f"Invalid Attribute ID {cur_id}")

    form.attribute_content.data = attribute.attribute_content

    return render_template("modal_add_attribute.html", form=form, attribute=attribute)

