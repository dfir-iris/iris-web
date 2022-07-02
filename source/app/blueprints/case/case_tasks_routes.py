#!/usr/bin/env python3
#
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

import marshmallow
# IMPORTS ------------------------------------------------
from datetime import datetime
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from flask_wtf import FlaskForm

from app import db
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_tasks_db import add_task
from app.datamgmt.case.case_tasks_db import get_task
from app.datamgmt.case.case_tasks_db import get_tasks
from app.datamgmt.case.case_tasks_db import get_tasks_status
from app.datamgmt.case.case_tasks_db import update_task_status
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import get_tasks_state
from app.datamgmt.states import update_tasks_state
from app.forms import CaseTaskForm
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.models.authorization import User
from app.models.models import CaseTasks
from app.schema.marshables import CaseTaskSchema
from app.util import ac_api_case_requires
from app.util import ac_case_requires
from app.util import response_error
from app.util import response_success

case_tasks_blueprint = Blueprint('case_tasks',
                                 __name__,
                                 template_folder='templates')


# CONTENT ------------------------------------------------
@case_tasks_blueprint.route('/case/tasks', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_tasks(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_tasks.case_tasks', cid=caseid, redirect=True))

    form = FlaskForm()
    case = get_case(caseid)

    return render_template("case_tasks.html", case=case, form=form)


@case_tasks_blueprint.route('/case/tasks/list', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_get_tasks(caseid):
    ct = get_tasks(caseid)

    if ct:
        output = [c._asdict() for c in ct]
    else:
        output = []

    ret = {
        "tasks_status": get_tasks_status(),
        "tasks": output,
        "state": get_tasks_state(caseid=caseid)
    }

    return response_success("", data=ret)


@case_tasks_blueprint.route('/case/tasks/state', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_get_tasks_state(caseid):
    os = get_tasks_state(caseid=caseid)
    if os:
        return response_success(data=os)
    else:
        return response_error('No tasks state for this case.')


@case_tasks_blueprint.route('/case/tasks/status/update/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_task_statusupdate(cur_id, caseid):

    task = get_task(task_id=cur_id, caseid=caseid)
    if not task:
        return response_error("Invalid task ID for this case")

    if request.is_json:

        if update_task_status(request.json.get('task_status_id'), cur_id, caseid):
            task_schema = CaseTaskSchema()

            return response_success("Task status updated", data=task_schema.dump(task))
        else:
            return response_error("Invalid status")

    else:
        return response_error("Invalid request")


@case_tasks_blueprint.route('/case/tasks/add/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.full_access)
def case_add_task_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_tasks.case_tasks', cid=caseid, redirect=True))

    task = CaseTasks()
    task.custom_attributes = get_default_custom_attributes('task')
    form = CaseTaskForm()
    form.task_assignee_id.choices = [(user.id, user.name) for user in
                                     User.query.filter(User.active == True).order_by(User.name).all()]
    form.task_status_id.choices = [(a.id, a.status_name) for a in get_tasks_status()]

    return render_template("modal_add_case_task.html", form=form, task=task, uid=current_user.id, user_name=None,
                           attributes=task.custom_attributes)


@case_tasks_blueprint.route('/case/tasks/add', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_add_task(caseid):

    try:
        # validate before saving
        task_schema = CaseTaskSchema()
        request_data = call_modules_hook('on_preload_task_create', data=request.get_json(), caseid=caseid)

        task = task_schema.load(request_data)

        ctask = add_task(task=task,
                         user_id=current_user.id,
                         caseid=caseid
                         )

        ctask = call_modules_hook('on_postload_task_create', data=ctask, caseid=caseid)

        if ctask:
            track_activity("added task {}".format(ctask.task_title), caseid=caseid)
            return response_success("Task '{}' added".format(ctask.task_title), data=task_schema.dump(ctask))

        return response_error("Unable to create task for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@case_tasks_blueprint.route('/case/tasks/<int:cur_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only)
def case_task_view(cur_id, caseid):
    task = get_task(task_id=cur_id, caseid=caseid)
    if not task:
        return response_error("Invalid task ID for this case")

    task_schema = CaseTaskSchema()

    return response_success(data=task_schema.dump(task))


@case_tasks_blueprint.route('/case/tasks/<int:cur_id>/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only)
def case_task_view_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_tasks.case_tasks', cid=caseid, redirect=True))

    form = CaseTaskForm()
    task = get_task(task_id=cur_id, caseid=caseid)
    form.task_assignee_id.choices = [(user.id, user.name) for user in
                                     User.query.filter(User.active == True).order_by(User.name).all()]
    form.task_status_id.choices = [(a.id, a.status_name) for a in get_tasks_status()]

    if not task:
        return response_error("Invalid task ID for this case")

    form.task_title.render_kw = {'value': task.task_title}
    form.task_description.data = task.task_description
    user_name, = User.query.with_entities(User.name).filter(User.id == task.task_userid_update).first()

    return render_template("modal_add_case_task.html", form=form, task=task,
                           uid=task.task_assignee_id, user_name=user_name, attributes=task.custom_attributes)


@case_tasks_blueprint.route('/case/tasks/update/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_edit_task(cur_id, caseid):

    try:
        task = get_task(task_id=cur_id, caseid=caseid)
        if not task:
            return response_error("Invalid task ID for this case")

        request_data = call_modules_hook('on_preload_task_update', data=request.get_json(), caseid=caseid)

        # validate before saving
        task_schema = CaseTaskSchema()

        request_data['id'] = cur_id
        task = task_schema.load(request_data, instance=task)

        task.task_userid_update = current_user.id
        task.task_last_update = datetime.utcnow()

        update_tasks_state(caseid=caseid)

        db.session.commit()

        task = call_modules_hook('on_postload_task_update', data=task, caseid=caseid)

        if task:
            track_activity("updated task {} (status {})".format(task.task_title, task.task_status_id), caseid=caseid)
            return response_success("Task '{}' updated".format(task.task_title), data=task_schema.dump(task))

        return response_error("Unable to update task for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@case_tasks_blueprint.route('/case/tasks/delete/<int:cur_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_edit_delete(cur_id, caseid):

    call_modules_hook('on_preload_task_delete', data=cur_id, caseid=caseid)
    task = get_task(task_id=cur_id, caseid=caseid)
    if not task:
        return response_error("Invalid task ID for this case")

    CaseTasks.query.filter(CaseTasks.id == cur_id, CaseTasks.task_case_id == caseid).delete()

    update_tasks_state(caseid=caseid)

    call_modules_hook('on_postload_task_delete', data=cur_id, caseid=caseid)

    track_activity("deleted task ID {}".format(cur_id))

    return response_success("Task deleted")

