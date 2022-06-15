#!/usr/bin/env python3
#
#  IRIS Source Code
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
from flask import Blueprint
from flask import render_template
from flask import url_for
from flask_wtf import FlaskForm
from werkzeug.utils import redirect

from app.datamgmt.manage.manage_groups_db import get_groups_list
from app.datamgmt.manage.manage_groups_db import get_groups_list_hr_perms
from app.util import admin_required
from app.util import api_admin_required
from app.util import response_success

manage_groups_blueprint = Blueprint(
        'manage_groups',
        __name__,
        template_folder='templates'
    )


@manage_groups_blueprint.route('/manage/groups/list', methods=['GET'])
@api_admin_required
def manage_ac_index(caseid):
    groups = get_groups_list_hr_perms()

    return response_success('', data=groups)
