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

from flask import Blueprint, send_file

from app.configuration import PG_SERVER_, PG_PORT_, PGA_ACCOUNT_, PGA_PASSWD_
from app.iris_engine.utils.tracker import track_activity
from app.util import FileRemover, response_error, api_admin_required

manage_adv_blueprint = Blueprint(
    'manage_adv',
    __name__,
    template_folder='templates'
)

file_remover = FileRemover()


@manage_adv_blueprint.route('/manage/advanced/backup/db', methods=['GET'])
@api_admin_required
def manage_adv_back_db(caseid):
    try:
        tmp_dir = tempfile.mkdtemp()
        # Make a backup
        args = ['/usr/bin/pg_dump', '-h{}'.format(PG_SERVER_), '-p{}'.format(PG_PORT_), '-diris_db', '-U{}'.format(PGA_ACCOUNT_), '-W{}'.format(PGA_PASSWD_)]

        with open(os.path.join(tmp_dir, "iris_backup.sql"), 'w') as f:
            process = subprocess.Popen(args, stdout=f)

            stdout, stderr = process.communicate()

        resp = send_file(os.path.join(tmp_dir, "iris_backup.sql"), as_attachment=True)

        file_remover.cleanup_once_done(resp, tmp_dir)

        track_activity("backed up database")

        return response_error("Uncaught error. {}".format(stdout))

    except Exception as e:
        return response_error("Error {}".format(e))
