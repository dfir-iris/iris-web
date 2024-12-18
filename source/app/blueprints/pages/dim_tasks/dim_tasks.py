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
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import url_for
from flask_wtf import FlaskForm

import app
from app.models.authorization import CaseAccessLevel
from app.models.authorization import Permissions
from app.blueprints.access_controls import ac_case_requires
from app.blueprints.access_controls import ac_requires
from app.blueprints.responses import response_error
from app.business.dim_tasks import dim_tasks_get

dim_tasks_blueprint = Blueprint(
    'dim_tasks',
    __name__,
    template_folder='templates'
)

basedir = os.path.abspath(os.path.dirname(app.__file__))


@dim_tasks_blueprint.route('/dim/tasks', methods=['GET'])
@ac_requires(Permissions.standard_user)
def dim_index(caseid: int, url_redir):
    if url_redir:
        return redirect(url_for('dim.dim_index', cid=caseid))

    form = FlaskForm()

    return render_template('dim_tasks.html', form=form)


@dim_tasks_blueprint.route('/dim/tasks/status/<task_id>', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def task_status(task_id, caseid, url_redir):
    if url_redir:
        return response_error('Invalid request')

    task_info = dim_tasks_get(task_id)
    return render_template('modal_task_info.html', data=task_info)
