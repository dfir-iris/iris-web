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
from app.models.models import AssetsType
from app.forms import AddAssetForm
from app import db

from app.util import response_success, response_error, login_required, admin_required, api_admin_required

from source.app.datamgmt.case.case_assets_db import get_analysis_status_list
from source.app.util import api_login_required

manage_anastatus_blueprint = Blueprint('manage_anastatus',
                                    __name__,
                                    template_folder='templates')


# CONTENT ------------------------------------------------
@manage_anastatus_blueprint.route('/manage/analysis-status/list', methods=['GET'])
@api_login_required
def list_anastatus(caseid):
    lstatus = get_analysis_status_list()
    return response_success("", data=lstatus)

# TODO : Add management of analysis status
