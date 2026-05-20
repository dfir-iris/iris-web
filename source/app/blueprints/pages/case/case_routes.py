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
from flask import url_for
from flask_wtf import FlaskForm

from app import app
from app.datamgmt.case.case_db import case_get_desc_crc
from app.datamgmt.case.case_db import get_activities_report_template
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_db import get_case_report_template
from app.datamgmt.case.case_db import get_case_tags
from app.datamgmt.manage.manage_groups_db import get_groups_list
from app.forms import PipelinesCaseForm
from app.iris_engine.access_control.utils import ac_get_all_access_level
from app.iris_engine.module_handler.module_handler import list_available_pipelines
from app.models.cases import CaseStatus
from app.models.authorization import CaseAccessLevel
from app.blueprints.access_controls import ac_case_requires

case_blueprint = Blueprint('case',
                           __name__,
                           template_folder='templates')

event_tags = ["Network", "Server", "ActiveDirectory", "Computer", "Malware", "User Interaction"]


log = app.logger


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
