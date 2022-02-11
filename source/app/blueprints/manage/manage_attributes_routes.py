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

    # Return default page of case management
    return render_template('manage_attributes.html', form=form)

