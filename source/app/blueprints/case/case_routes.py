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

import binascii
import marshmallow
# IMPORTS ------------------------------------------------
import traceback
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from flask_socketio import emit
from flask_socketio import join_room
from flask_wtf import FlaskForm
from sqlalchemy import and_
from sqlalchemy import desc

from app import app
from app import db
from app import socket_io
from app.blueprints.case.case_assets_routes import case_assets_blueprint
from app.blueprints.case.case_graphs_routes import case_graph_blueprint
from app.blueprints.case.case_ioc_routes import case_ioc_blueprint
from app.blueprints.case.case_notes_routes import case_notes_blueprint
from app.blueprints.case.case_rfiles_routes import case_rfiles_blueprint
from app.blueprints.case.case_tasks_routes import case_tasks_blueprint
from app.blueprints.case.case_timeline_routes import case_timeline_blueprint
from app.datamgmt.case.case_db import case_exists, get_review_id_from_name
from app.datamgmt.case.case_db import case_get_desc_crc
from app.datamgmt.case.case_db import get_activities_report_template
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_db import get_case_report_template
from app.datamgmt.case.case_db import get_case_tags
from app.datamgmt.manage.manage_groups_db import add_case_access_to_group
from app.datamgmt.manage.manage_groups_db import get_group_with_members
from app.datamgmt.manage.manage_groups_db import get_groups_list
from app.datamgmt.manage.manage_users_db import get_user
from app.datamgmt.manage.manage_users_db import get_users_list_restricted_from_case
from app.datamgmt.manage.manage_users_db import set_user_case_access
from app.datamgmt.reporter.report_db import export_case_json
from app.forms import PipelinesCaseForm
from app.iris_engine.access_control.utils import ac_get_all_access_level, ac_fast_check_current_user_has_case_access, \
    ac_fast_check_user_has_case_access
from app.iris_engine.access_control.utils import ac_set_case_access_for_users
from app.iris_engine.module_handler.module_handler import list_available_pipelines
from app.iris_engine.utils.tracker import track_activity
from app.models import CaseStatus, ReviewStatusList
from app.models import UserActivity
from app.models.authorization import CaseAccessLevel
from app.models.authorization import User
from app.schema.marshables import TaskLogSchema, CaseSchema, CaseDetailsSchema
from app.util import ac_api_case_requires, add_obj_history_entry
from app.util import ac_case_requires
from app.util import ac_socket_requires
from app.util import response_error
from app.util import response_success

app.register_blueprint(case_timeline_blueprint)
app.register_blueprint(case_notes_blueprint)
app.register_blueprint(case_assets_blueprint)
app.register_blueprint(case_ioc_blueprint)
app.register_blueprint(case_rfiles_blueprint)
app.register_blueprint(case_graph_blueprint)
app.register_blueprint(case_tasks_blueprint)

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


@case_blueprint.route('/case/exists', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_exists_r(caseid):

    if case_exists(caseid):
        return response_success('Case exists')
    else:
        return response_error('Case does not exist', 404)


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
def socket_summary_onchange(message):

    emit('clear_buffer', message)


@socket_io.on('join')
@ac_socket_requires(CaseAccessLevel.full_access)
def get_message(data):

    room = data['channel']
    join_room(room=room)
    emit('join', {'message': f"{current_user.user} just joined"}, room=room)


@case_blueprint.route('/case/summary/update', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def desc_fetch(caseid):

    js_data = request.get_json()
    case = get_case(caseid)
    if not case:
        return response_error('Invalid case ID')

    case.description = js_data.get('case_description')
    crc = binascii.crc32(case.description.encode('utf-8'))
    db.session.commit()
    track_activity("updated summary", caseid)

    if not request.cookies.get('session'):
        # API call so we propagate the message to everyone
        data = {
            "case_description": case.description,
            "last_saved": current_user.user
        }
        socket_io.emit('save', data, to=f"case-{caseid}")

    return response_success("Summary updated", data=crc)


@case_blueprint.route('/case/summary/fetch', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def summary_fetch(caseid):
    desc_crc32, description = case_get_desc_crc(caseid)

    return response_success("Summary fetch", data={'case_description': description, 'crc32': desc_crc32})


@case_blueprint.route('/case/activities/list', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def activity_fetch(caseid):
    ua = UserActivity.query.with_entities(
        UserActivity.activity_date,
        User.name,
        UserActivity.activity_desc,
        UserActivity.is_from_api
    ).filter(and_(
        UserActivity.case_id == caseid,
        UserActivity.display_in_ui == True
    )).join(
        UserActivity.user
    ).order_by(
        desc(UserActivity.activity_date)
    ).limit(40).all()

    output = [a._asdict() for a in ua]

    return response_success("", data=output)


@case_blueprint.route("/case/export", methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def export_case(caseid):
    return response_success('', data=export_case_json(caseid))


@case_blueprint.route("/case/meta", methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def meta_case(caseid):
    case_details = get_case(caseid)
    return response_success('', data= CaseDetailsSchema().dump(case_details))


@case_blueprint.route('/case/tasklog/add', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_add_tasklog(caseid):

    log_schema = TaskLogSchema()

    try:

        log_data = log_schema.load(request.get_json())

        ua = track_activity(log_data.get('log_content'), caseid, user_input=True)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    return response_success("Log saved", data=ua)


@case_blueprint.route('/case/users/list', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_get_users(caseid):

    users = get_users_list_restricted_from_case(caseid)

    return response_success(data=users)


@case_blueprint.route('/case/groups/access/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.full_access)
def groups_cac_view(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case.case_r', cid=caseid, redirect=True))

    groups = get_groups_list()
    access_levels = ac_get_all_access_level()

    return render_template('modal_cac_to_groups.html', groups=groups, access_levels=access_levels, caseid=caseid)


@case_blueprint.route('/case/access/set-group', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def group_cac_set_case(caseid):

    data = request.get_json()
    if not data:
        return response_error("Invalid request")

    if data.get('case_id') != caseid:
        return response_error("Inconsistent case ID")

    case = get_case(caseid)
    if not case:
        return response_error("Invalid case ID")

    group_id = data.get('group_id')
    access_level = data.get('access_level')

    group = get_group_with_members(group_id)

    try:

        success, logs = add_case_access_to_group(group, [data.get('case_id')], access_level)

        if success:
            success, logs = ac_set_case_access_for_users(group.group_members, caseid, access_level)

    except Exception as e:
        log.error("Error while setting case access for group: {}".format(e))
        log.error(traceback.format_exc())
        return response_error(msg=str(e))

    if success:
        track_activity("case access set to {} for group {}".format(data.get('access_level'), group_id), caseid)
        add_obj_history_entry(case, "access changed to {} for group {}".format(data.get('access_level'), group_id),
                              commit=True)

        return response_success(msg=logs)

    return response_error(msg=logs)


@case_blueprint.route('/case/access/set-user', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def user_cac_set_case(caseid):

    data = request.get_json()
    if not data:
        return response_error("Invalid request")

    if data.get('user_id') == current_user.id:
        return response_error("I can't let you do that, Dave")

    user = get_user(data.get('user_id'))
    if not user:
        return response_error("Invalid user ID")

    if data.get('case_id') != caseid:
        return response_error("Inconsistent case ID")

    case = get_case(caseid)
    if not case:
        return response_error('Invalid case ID')

    try:

        success, logs = set_user_case_access(user.id, data.get('case_id'), data.get('access_level'))
        track_activity("case access set to {} for user {}".format(data.get('access_level'), user.name), caseid)
        add_obj_history_entry(case, "access changed to {} for user {}".format(data.get('access_level'), user.name))

        db.session.commit()

    except Exception as e:
        log.error("Error while setting case access for user: {}".format(e))
        log.error(traceback.format_exc())
        return response_error(msg=str(e))

    if success:
        return response_success(msg=logs)

    return response_error(msg=logs)


@case_blueprint.route('/case/update-status', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_update_status(caseid):

    case = get_case(caseid)
    if not case:
        return response_error('Invalid case ID')

    status = request.get_json().get('status_id')
    case_status = set(item.value for item in CaseStatus)

    try:
        status = int(status)
    except ValueError:
        return response_error('Invalid status')
    except TypeError:
        return response_error('Invalid status. Expected int')

    if status not in case_status:
        return response_error('Invalid status')

    case.status_id = status
    add_obj_history_entry(case, f'status updated to {CaseStatus(status).name}')

    db.session.commit()

    return response_success("Case status updated", data=case.status_id)


@case_blueprint.route('/case/md-helper', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_md_helper(caseid, url_redir):

    return render_template('case_md_helper.html')


@case_blueprint.route('/case/review/update', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_review(caseid):

    case = get_case(caseid)
    if not case:
        return response_error('Invalid case ID')

    action = request.get_json().get('action')
    reviewer_id = request.get_json().get('reviewer_id')

    if action == 'start':
        review_name = ReviewStatusList.review_in_progress
    elif action == 'cancel' or action == 'request':
        review_name = ReviewStatusList.pending_review
    elif action == 'no_review':
        review_name = ReviewStatusList.no_review_required
    elif action == 'to_review':
        review_name = ReviewStatusList.not_reviewed
    elif action == 'done':
        review_name = ReviewStatusList.reviewed
    else:
        return response_error('Invalid action')

    case.review_status_id = get_review_id_from_name(review_name)
    if reviewer_id:
        try:
            reviewer_id = int(reviewer_id)
        except ValueError:
            return response_error('Invalid reviewer ID')

        if not ac_fast_check_user_has_case_access(reviewer_id, caseid, [CaseAccessLevel.full_access]):
            return response_error('Invalid reviewer ID')

        case.reviewer_id = reviewer_id

    db.session.commit()

    add_obj_history_entry(case, f'review status updated to {review_name}')
    track_activity(f'review status updated to {review_name}', caseid)

    db.session.commit()

    return response_success("Case review updated", data=CaseSchema().dump(case))
