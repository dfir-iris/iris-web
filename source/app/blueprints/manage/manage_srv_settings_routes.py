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

import os
import subprocess
# IMPORTS ------------------------------------------------
import tempfile

from flask import Blueprint, send_file, url_for, render_template
from flask_wtf import FlaskForm
from werkzeug.utils import redirect

from app.configuration import PG_SERVER_, PG_PORT_, PGA_ACCOUNT_, PGA_PASSWD_
from app.iris_engine.utils.tracker import track_activity
from app.util import FileRemover, response_error, api_admin_required, admin_required

manage_srv_settings_blueprint = Blueprint(
    'manage_srv_settings_blueprint',
    __name__,
    template_folder='templates'
)


@manage_srv_settings_blueprint.route('/manage/settings', methods=['GET'])
@admin_required
def manage_settings(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_srv_settings_blueprint.manage_settings', cid=caseid))

    form = FlaskForm()

    # Return default page of case management
    return render_template('manage_srv_settings.html', form=form)
