#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

import marshmallow
from datetime import datetime
from datetime import timedelta
from oic.oauth2.exception import GrantError

from flask import Blueprint
from flask import session
from flask import request
from flask import redirect
from flask_login import logout_user

from app.db import db
from app import app
from app import oidc_client

from app.blueprints.rest.endpoints import endpoint_deprecated
from app.blueprints.iris_user import iris_current_user
from app.datamgmt.case.case_db import list_user_reviews
from app.datamgmt.case.case_db import list_user_cases
from app.datamgmt.case.case_tasks_db import get_tasks_status
from app.datamgmt.global_tasks import list_global_tasks
from app.datamgmt.global_tasks import get_global_task
from app.datamgmt.case.case_tasks_db import list_user_tasks
from app.forms import CaseGlobalTaskForm
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import User
from app.models.cases import Cases
from app.models.models import CaseTasks
from app.models.models import GlobalTasks
from app.models.models import TaskStatus
from app.schema.marshables import CaseTaskSchema
from app.schema.marshables import CaseDetailsSchema
from app.schema.marshables import GlobalTasksSchema
from app.blueprints.access_controls import ac_requires_case_identifier
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success
from app.blueprints.access_controls import is_authentication_oidc
from app.blueprints.access_controls import not_authenticated_redirection_url


log = app.logger


dashboard_rest_blueprint = Blueprint(
    'dashboard_rest',
    __name__,
    template_folder='templates'
)


# Logout user
@dashboard_rest_blueprint.route('/logout')
def logout():
    """
    Logout function. Erase its session and redirect to index i.e login
    :return: Page
    """
    if session['current_case']:
        iris_current_user.ctx_case = session['current_case']['case_id']
        db.session.commit()

    if is_authentication_oidc():
        if oidc_client.provider_info.get("end_session_endpoint"):
            try:
                logout_request = oidc_client.construct_EndSessionRequest(
                    state=session["oidc_state"])
                logout_url = logout_request.request(
                    oidc_client.provider_info["end_session_endpoint"])
                track_activity(f"user '{iris_current_user.user}' is been logged-out", ctx_less=True, display_in_ui=False)
                logout_user()
                session.clear()
                return redirect(logout_url)
            except GrantError:
                track_activity(
                    f"no oidc session found for user '{iris_current_user.user}', skipping oidc provider logout and continuing to logout local user",
                    ctx_less=True,
                    display_in_ui=False
                )

    track_activity(f"user '{iris_current_user.user}' is been logged-out",
                   ctx_less=True, display_in_ui=False)
    logout_user()
    session.clear()

    return redirect(not_authenticated_redirection_url('/'))


@dashboard_rest_blueprint.route('/dashboard/case_charts', methods=['GET'])
@ac_api_requires()
def get_cases_charts():
    """
    Get case charts
    :return: JSON
    """
    res = Cases.query.with_entities(
        Cases.open_date
    ).filter(
        Cases.open_date > (datetime.utcnow() - timedelta(days=365))
    ).order_by(
        Cases.open_date
    ).all()
    retr = [[], []]
    rk = {}
    for case in res:
        month = f"{case.open_date.day}/{case.open_date.month}/{case.open_date.year}"

        if month in rk:
            rk[month] += 1
        else:
            rk[month] = 1

        retr = [list(rk.keys()), list(rk.values())]

    return response_success("", retr)


@dashboard_rest_blueprint.route('/global/tasks/list', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/global-tasks')
@ac_api_requires()
def get_gtasks():
    tasks_list = list_global_tasks()

    if tasks_list:
        output = [c._asdict() for c in tasks_list]
    else:
        output = []

    ret = {
        "tasks_status": get_tasks_status(),
        "tasks": output
    }

    return response_success("", data=ret)


@dashboard_rest_blueprint.route('/global/tasks/<int:cur_id>', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/global-tasks/{identifier}')
@ac_api_requires()
def view_gtask(cur_id):
    task = get_global_task(cur_id)
    if not task:
        return response_error(f'Global task ID {cur_id} not found')

    return response_success('', data=task._asdict())


@dashboard_rest_blueprint.route('/user/tasks/status/update', methods=['POST'])
@endpoint_deprecated('PUT', '/api/v2/cases/{case_identifier}/tasks/{identifier}')
@ac_api_requires()
@ac_requires_case_identifier()
def utask_statusupdate(caseid):
    jsdata = request.get_json()
    if not jsdata:
        return response_error("Invalid request")

    jsdata = request.get_json()
    if not jsdata:
        return response_error("Invalid request")

    case_id = jsdata.get('case_id') if jsdata.get('case_id') else caseid
    task_id = jsdata.get('task_id')
    task = CaseTasks.query.filter(
        CaseTasks.id == task_id, CaseTasks.task_case_id == case_id).first()
    if not task:
        return response_error(f"Invalid case task ID {task_id} for case {case_id}")

    status_id = jsdata.get('task_status_id')
    status = TaskStatus.query.filter(TaskStatus.id == status_id).first()
    if not status:
        return response_error(f"Invalid task status ID {status_id}")

    task.task_status_id = status_id
    try:

        db.session.commit()

    except Exception as e:
        return response_error(f"Unable to update task. Error {e}")

    task_schema = CaseTaskSchema()
    return response_success("Updated", data=task_schema.dump(task))


@dashboard_rest_blueprint.route('/global/tasks/add', methods=['POST'])
@endpoint_deprecated('POST', '/api/v2/global-tasks')
@ac_api_requires()
@ac_requires_case_identifier()
def add_gtask(caseid):
    try:

        gtask_schema = GlobalTasksSchema()

        request_data = call_modules_hook('on_preload_global_task_create', request.get_json(), caseid=caseid)

        gtask = gtask_schema.load(request_data)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    gtask.task_userid_update = iris_current_user.id
    gtask.task_open_date = datetime.utcnow()
    gtask.task_last_update = datetime.utcnow()
    gtask.task_last_update = datetime.utcnow()

    try:

        db.session.add(gtask)
        db.session.commit()

    except Exception as e:
        return response_error(msg="Data error", data=e.__str__())

    gtask = call_modules_hook('on_postload_global_task_create', gtask, caseid=caseid)
    track_activity(f"created new global task \'{gtask.task_title}\'", caseid=caseid)

    return response_success('Task added', data=gtask_schema.dump(gtask))


@dashboard_rest_blueprint.route('/global/tasks/update/<int:cur_id>', methods=['POST'])
@endpoint_deprecated('PUT', '/api/v2/global-tasks/{identifier}')
@ac_api_requires()
@ac_requires_case_identifier()
def edit_gtask(cur_id, caseid):
    form = CaseGlobalTaskForm()
    task = GlobalTasks.query.filter(GlobalTasks.id == cur_id).first()
    form.task_assignee_id.choices = [(user.id, user.name) for user in User.query.filter(
        User.active == True).order_by(User.name).all()]
    form.task_status_id.choices = [(a.id, a.status_name)
                                   for a in get_tasks_status()]

    if not task:
        return response_error(msg="Data error", data="Invalid task ID")

    try:
        gtask_schema = GlobalTasksSchema()

        request_data = call_modules_hook('on_preload_global_task_update', request.get_json(), caseid=caseid)

        gtask = gtask_schema.load(request_data, instance=task)
        gtask.task_userid_update = iris_current_user.id
        gtask.task_last_update = datetime.utcnow()

        db.session.commit()

        gtask = call_modules_hook(
            'on_postload_global_task_update', data=gtask, caseid=caseid)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    track_activity(f"updated global task {task.task_title} (status {task.task_status_id})", caseid=caseid)

    return response_success('Task updated', data=gtask_schema.dump(gtask))


@dashboard_rest_blueprint.route('/global/tasks/delete/<int:cur_id>', methods=['POST'])
@endpoint_deprecated('DELETE', '/api/v2/global-tasks/{identifier}')
@ac_api_requires()
@ac_requires_case_identifier()
def gtask_delete(cur_id, caseid):
    call_modules_hook('on_preload_global_task_delete', cur_id, caseid=caseid)

    if not cur_id:
        return response_error("Missing parameter")

    data = GlobalTasks.query.filter(GlobalTasks.id == cur_id).first()
    if not data:
        return response_error("Invalid global task ID")

    GlobalTasks.query.filter(GlobalTasks.id == cur_id).delete()
    db.session.commit()

    call_modules_hook('on_postload_global_task_delete', request.get_json(), caseid=caseid)
    track_activity(f"deleted global task ID {cur_id}", caseid=caseid)

    return response_success("Task deleted")


@dashboard_rest_blueprint.route('/user/cases/list', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/cases?case_owner_id=<user_id>')
@ac_api_requires()
def list_own_cases():
    cases = list_user_cases(
        iris_current_user.id,
        request.args.get('show_closed', 'false', type=str).lower() == 'true'
    )

    return response_success("", data=CaseDetailsSchema(many=True).dump(cases))


@dashboard_rest_blueprint.route('/user/tasks/list', methods=['GET'])
@ac_api_requires()
def get_utasks():
    ct = list_user_tasks(iris_current_user.id)

    if ct:
        output = [c._asdict() for c in ct]
    else:
        output = []

    ret = {
        "tasks_status": get_tasks_status(),
        "tasks": output
    }

    return response_success("", data=ret)


@dashboard_rest_blueprint.route('/user/reviews/list', methods=['GET'])
@ac_api_requires()
def get_reviews():
    ct = list_user_reviews(iris_current_user.id)

    if ct:
        output = [c._asdict() for c in ct]
    else:
        output = []

    return response_success("", data=output)
