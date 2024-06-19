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

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from flask_socketio import emit
from flask_socketio import join_room
from flask_wtf import FlaskForm

from app import app
from app import socket_io
from app.blueprints.case.case_assets_routes import case_assets_blueprint
from app.blueprints.rest.case.case_assets_routes import case_assets_rest_blueprint
from app.blueprints.case.case_graphs_routes import case_graph_blueprint
from app.blueprints.rest.case.case_graphs_routes import case_graph_rest_blueprint
from app.blueprints.case.case_ioc_routes import case_ioc_blueprint
from app.blueprints.rest.case.case_ioc_routes import case_ioc_rest_blueprint
from app.blueprints.case.case_notes_routes import case_notes_blueprint
from app.blueprints.rest.case.case_notes_routes import case_notes_rest_blueprint
from app.blueprints.case.case_rfiles_routes import case_rfiles_blueprint
from app.blueprints.rest.case.case_evidences_routes import case_evidences_rest_blueprint
from app.blueprints.case.case_tasks_routes import case_tasks_blueprint
from app.blueprints.rest.case.case_tasks_routes import case_tasks_rest_blueprint
from app.blueprints.case.case_timeline_routes import case_timeline_blueprint
from app.datamgmt.case.case_db import case_get_desc_crc
from app.datamgmt.case.case_db import get_activities_report_template
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_db import get_case_report_template
from app.datamgmt.case.case_db import get_case_tags
from app.datamgmt.manage.manage_groups_db import get_groups_list
from app.forms import PipelinesCaseForm
from app.iris_engine.access_control.utils import ac_get_all_access_level
from app.iris_engine.module_handler.module_handler import list_available_pipelines
from app.models import CaseStatus
from app.models.authorization import CaseAccessLevel
from app.util import ac_case_requires
from app.util import ac_socket_requires

app.register_blueprint(case_timeline_blueprint)
app.register_blueprint(case_notes_blueprint)
app.register_blueprint(case_notes_rest_blueprint)
app.register_blueprint(case_assets_blueprint)
app.register_blueprint(case_assets_rest_blueprint)
app.register_blueprint(case_ioc_blueprint)
app.register_blueprint(case_ioc_rest_blueprint)
app.register_blueprint(case_rfiles_blueprint)
app.register_blueprint(case_evidences_rest_blueprint)
app.register_blueprint(case_graph_blueprint)
app.register_blueprint(case_graph_rest_blueprint)
app.register_blueprint(case_tasks_blueprint)
app.register_blueprint(case_tasks_rest_blueprint)

case_blueprint = Blueprint('case',
                           __name__,
                           template_folder='templates')

event_tags = ["Network", "Server", "ActiveDirectory", "Computer", "Malware", "User Interaction"]


log = app.logger


# CONTENT ------------------------------------------------
@case_blueprint.route('/case', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_r(caseid, url_redir):

    if url_redir:
        return redirect(url_for('case.case_r', cid=caseid, redirect=True))

    case = get_case(caseid)
    setattr(case, 'case_tags', get_case_tags(caseid))
    form = FlaskForm()

    reports = get_case_report_template()
    reports = [row for row in reports]

    reports_act = get_activities_report_template()
    reports_act = [row for row in reports_act]

    if not case:
        return render_template('select_case.html')

    desc_crc32, description = case_get_desc_crc(caseid)
    setattr(case, 'status_name', CaseStatus(case.status_id).name.replace('_', ' ').title())

    return render_template('case.html', case=case, desc=description, crc=desc_crc32,
                           reports=reports, reports_act=reports_act, form=form)


@case_blueprint.route('/case/pipelines-modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.full_access)
def case_pipelines_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case.case_r', cid=caseid, redirect=True))

    case = get_case(caseid)

    form = PipelinesCaseForm()

    pl = list_available_pipelines()

    form.pipeline.choices = [("{}-{}".format(ap[0], ap[1]['pipeline_internal_name']),
                                         ap[1]['pipeline_human_name'])for ap in pl]

    # Return default page of case management
    pipeline_args = [("{}-{}".format(ap[0], ap[1]['pipeline_internal_name']),
                      ap[1]['pipeline_human_name'], ap[1]['pipeline_args'])for ap in pl]

    return render_template('modal_case_pipelines.html', case=case, form=form, pipeline_args=pipeline_args)


@socket_io.on('change')
@ac_socket_requires(CaseAccessLevel.full_access)
def socket_summary_onchange(data):

    data['last_change'] = current_user.user
    emit('change', data, to=data['channel'], skip_sid=request.sid)


@socket_io.on('save')
@ac_socket_requires(CaseAccessLevel.full_access)
def socket_summary_onsave(data):

    data['last_saved'] = current_user.user
    emit('save', data, to=data['channel'], skip_sid=request.sid)


@socket_io.on('clear_buffer')
@ac_socket_requires(CaseAccessLevel.full_access)
def socket_summary_on_clear_buffer(message):

    emit('clear_buffer', message)


@socket_io.on('join')
@ac_socket_requires(CaseAccessLevel.full_access)
def get_message(data):

    room = data['channel']
    join_room(room=room)
    emit('join', {'message': f"{current_user.user} just joined"}, room=room)


@case_blueprint.route('/case/groups/access/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.full_access)
def groups_cac_view(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case.case_r', cid=caseid, redirect=True))

    groups = get_groups_list()
    access_levels = ac_get_all_access_level()

    return render_template('modal_cac_to_groups.html', groups=groups, access_levels=access_levels, caseid=caseid)


@case_blueprint.route('/case/md-helper', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_md_helper(caseid, url_redir):

    return render_template('case_md_helper.html')
