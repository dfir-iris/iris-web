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

import marshmallow
# IMPORTS ------------------------------------------------
from datetime import datetime
from datetime import timedelta
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask_login import current_user
from flask_login import logout_user
from flask_wtf import FlaskForm
from sqlalchemy import distinct
import requests

from app import app
from app import db
from app.datamgmt.dashboard.dashboard_db import get_global_task, list_user_cases, list_user_reviews
from app.datamgmt.dashboard.dashboard_db import get_tasks_status
from app.datamgmt.dashboard.dashboard_db import list_global_tasks
from app.datamgmt.dashboard.dashboard_db import list_user_tasks
from app.forms import CaseGlobalTaskForm
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import User
from app.models.cases import Cases
from app.models.models import CaseTasks
from app.models.models import GlobalTasks
from app.models.models import TaskStatus
from app.models.models import UserActivity
from app.schema.marshables import CaseTaskSchema, CaseSchema, CaseDetailsSchema
from app.schema.marshables import GlobalTasksSchema
from app.util import ac_api_requires
from app.util import ac_requires
from app.util import not_authenticated_redirection_url
from app.util import response_error
from app.util import response_success
from app.iris_engine.access_control.oidc_proxy_handler import oidc_proxy_logout
#from app.util import is_authentication_oidc_proxy
#from oauth2client.client import OAuth2Credentials

# CONTENT ------------------------------------------------
dashboard_blueprint = Blueprint(
    'index',
    __name__,
    template_folder='templates'
)


# Logout user
@dashboard_blueprint.route('/logout')
def logout():
    """
    Logout function. Erase its session and redirect to index i.e login
    :return: Page
    """
    try:
        track_activity("user '{}' want log-out".format(current_user.user), ctx_less=True, display_in_ui=False)
        if 'current_case' in session.keys() and session['current_case']:
            current_user.ctx_case = session['current_case']['case_id']
            current_user.ctx_human_case = session['current_case']['case_name']
            db.session.commit()
            
        if current_user.is_authenticated:
            track_activity("user '{}' has been logged-out".format(current_user.user), ctx_less=True, display_in_ui=False)
            logout_user()
            if (app.config.get('AUTHENTICATION_TYPE')) == "oidc_proxy":
                oidc_proxy_logout()
    except Exception as e:
            track_activity("error loging out. Probably session not initated properly.", ctx_less=True, display_in_ui=False)

    return redirect('/login') #not_authenticated_redirection_url('/') #


@dashboard_blueprint.route('/dashboard/case_charts', methods=['GET'])
@ac_api_requires()
def get_cases_charts(caseid):
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
        month = "{}/{}/{}".format(case.open_date.day, case.open_date.month, case.open_date.year)

        if month in rk:
            rk[month] += 1
        else:
            rk[month] = 1

        retr = [list(rk.keys()), list(rk.values())]

    return response_success("", retr)


@dashboard_blueprint.route('/')
def root():
    if app.config['DEMO_MODE_ENABLED'] == 'True':
        return redirect(url_for('demo-landing.demo_landing'))

    return redirect(url_for('index.index'))

#@conditional_decorator(is_authentication_oidc_proxy(), oidc.require_login)
#@oidc.require_login
@dashboard_blueprint.route('/dashboard')
@ac_requires()
def index(caseid, url_redir):
    """
    Index page. Load the dashboard data, create the add customer form
    :return: Page
    """
    if url_redir:
        return redirect(url_for('index.index', cid=caseid if caseid is not None else 1, redirect=True))

    msg = None

    # Retrieve the dashboard data from multiple sources.
    # Quite fast as it is only counts.
    user_open_case = Cases.query.filter(
        Cases.owner_id == current_user.id,
        Cases.close_date == None
    ).count()

    try:
        data = {
            "user_open_count": user_open_case,
            "cases_open_count": Cases.query.filter(Cases.close_date == None).count(),
            "cases_count": Cases.query.with_entities(distinct(Cases.case_id)).count(),
        }
    except:
        return redirect('/login')
    
    # Create the customer form to be able to quickly add a customer
    form = FlaskForm()

    return render_template('index.html', data=data, form=form, msg=msg)


@dashboard_blueprint.route('/global/tasks/list', methods=['GET'])
@ac_api_requires()
def get_gtasks(caseid):

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


@dashboard_blueprint.route('/user/cases/list', methods=['GET'])
@ac_api_requires()
def list_own_cases(caseid):

    cases = list_user_cases(
        request.args.get('show_closed', 'false', type=str).lower() == 'true'
    )

    return response_success("", data=CaseDetailsSchema(many=True).dump(cases))


@dashboard_blueprint.route('/global/tasks/<int:cur_id>', methods=['GET'])
@ac_api_requires()
def view_gtask(cur_id, caseid):

    task = get_global_task(task_id=cur_id)
    if not task:
        return response_error(f'Global task ID {cur_id} not found')

    return response_success("", data=task._asdict())


@dashboard_blueprint.route('/user/tasks/list', methods=['GET'])
@ac_api_requires()
def get_utasks(caseid):

    ct = list_user_tasks()

    if ct:
        output = [c._asdict() for c in ct]
    else:
        output = []

    ret = {
        "tasks_status": get_tasks_status(),
        "tasks": output
    }

    return response_success("", data=ret)


@dashboard_blueprint.route('/user/reviews/list', methods=['GET'])
@ac_api_requires()
def get_reviews(caseid):

    ct = list_user_reviews()

    if ct:
        output = [c._asdict() for c in ct]
    else:
        output = []


    return response_success("", data=output)


@dashboard_blueprint.route('/user/tasks/status/update', methods=['POST'])
@ac_api_requires()
def utask_statusupdate(caseid):
    jsdata = request.get_json()
    if not jsdata:
        return response_error("Invalid request")

    jsdata = request.get_json()
    if not jsdata:
        return response_error("Invalid request")

    case_id = jsdata.get('case_id') if jsdata.get('case_id') else caseid
    task_id = jsdata.get('task_id')
    task = CaseTasks.query.filter(CaseTasks.id == task_id, CaseTasks.task_case_id == case_id).first()
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


@dashboard_blueprint.route('/global/tasks/add/modal', methods=['GET'])
@ac_api_requires()
def add_gtask_modal(caseid):
    task = GlobalTasks()

    form = CaseGlobalTaskForm()

    form.task_assignee_id.choices = [(user.id, user.name) for user in User.query.filter(User.active == True).order_by(User.name).all()]
    form.task_status_id.choices = [(a.id, a.status_name) for a in get_tasks_status()]

    return render_template("modal_add_global_task.html", form=form, task=task, uid=current_user.id, user_name=None)


@dashboard_blueprint.route('/global/tasks/add', methods=['POST'])
@ac_api_requires()
def add_gtask(caseid):

    try:

        gtask_schema = GlobalTasksSchema()

        request_data = call_modules_hook('on_preload_global_task_create', data=request.get_json(), caseid=caseid)

        gtask = gtask_schema.load(request_data)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)

    gtask.task_userid_update = current_user.id
    gtask.task_open_date = datetime.utcnow()
    gtask.task_last_update = datetime.utcnow()
    gtask.task_last_update = datetime.utcnow()

    try:

        db.session.add(gtask)
        db.session.commit()

    except Exception as e:
        return response_error(msg="Data error", data=e.__str__(), status=400)

    gtask = call_modules_hook('on_postload_global_task_create', data=gtask, caseid=caseid)
    track_activity("created new global task \'{}\'".format(gtask.task_title), caseid=caseid)

    return response_success('Task added', data=gtask_schema.dump(gtask))


@dashboard_blueprint.route('/global/tasks/update/<int:cur_id>/modal', methods=['GET'])
@ac_api_requires()
def edit_gtask_modal(cur_id, caseid):
    form = CaseGlobalTaskForm()
    task = GlobalTasks.query.filter(GlobalTasks.id == cur_id).first()
    form.task_assignee_id.choices = [(user.id, user.name) for user in
                                     User.query.filter(User.active == True).order_by(User.name).all()]
    form.task_status_id.choices = [(a.id, a.status_name) for a in get_tasks_status()]

    # Render the task
    form.task_title.render_kw = {'value': task.task_title}
    form.task_description.data = task.task_description
    user_name, = User.query.with_entities(User.name).filter(User.id == task.task_userid_update).first()

    return render_template("modal_add_global_task.html", form=form, task=task,
                           uid=task.task_assignee_id, user_name=user_name)


@dashboard_blueprint.route('/global/tasks/update/<int:cur_id>', methods=['POST'])
@ac_api_requires()
def edit_gtask(cur_id, caseid):

    form = CaseGlobalTaskForm()
    task = GlobalTasks.query.filter(GlobalTasks.id == cur_id).first()
    form.task_assignee_id.choices = [(user.id, user.name) for user in User.query.filter(User.active == True).order_by(User.name).all()]
    form.task_status_id.choices = [(a.id, a.status_name) for a in get_tasks_status()]

    if not task:
        return response_error(msg="Data error", data="Invalid task ID", status=400)

    try:
        gtask_schema = GlobalTasksSchema()

        request_data = call_modules_hook('on_preload_global_task_update', data=request.get_json(),
                                         caseid=caseid)

        gtask = gtask_schema.load(request_data, instance=task)
        gtask.task_userid_update = current_user.id
        gtask.task_last_update = datetime.utcnow()

        db.session.commit()

        gtask = call_modules_hook('on_postload_global_task_update', data=gtask, caseid=caseid)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)

    track_activity("updated global task {} (status {})".format(task.task_title, task.task_status_id), caseid=caseid)

    return response_success('Task updated', data=gtask_schema.dump(gtask))


@dashboard_blueprint.route('/global/tasks/delete/<int:cur_id>', methods=['POST'])
@ac_api_requires()
def gtask_delete(cur_id, caseid):

    call_modules_hook('on_preload_global_task_delete', data=cur_id, caseid=caseid)

    if not cur_id:
        return response_error("Missing parameter")

    data = GlobalTasks.query.filter(GlobalTasks.id == cur_id).first()
    if not data:
        return response_error("Invalid global task ID")

    GlobalTasks.query.filter(GlobalTasks.id == cur_id).delete()
    db.session.commit()

    call_modules_hook('on_postload_global_task_delete', data=request.get_json(), caseid=caseid)
    track_activity("deleted global task ID {}".format(cur_id), caseid=caseid)

    return response_success("Task deleted")
