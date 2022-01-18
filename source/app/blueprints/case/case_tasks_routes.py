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

# IMPORTS ------------------------------------------------
from datetime import datetime

import marshmallow
from flask import Blueprint, request
from flask import render_template, url_for, redirect
from flask_login import current_user
from flask_wtf import FlaskForm

from app import db
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_tasks_db import get_tasks, get_task, update_task_status, add_task, get_tasks_status
from app.datamgmt.states import get_tasks_state, update_tasks_state
from app.forms import CaseTaskForm
from app.models.models import User, CaseTasks
from app.schema.marshables import CaseTaskSchema
from app.util import response_success, response_error, login_required, api_login_required
from app.iris_engine.utils.tracker import track_activity

case_tasks_blueprint = Blueprint('case_tasks',
                                 __name__,
                                 template_folder='templates')


# CONTENT ------------------------------------------------
@case_tasks_blueprint.route('/case/tasks', methods=['GET'])
@login_required
def case_tasks(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_tasks.case_tasks', cid=caseid))

    form = FlaskForm()
    case = get_case(caseid)

    return render_template("case_tasks.html", case=case, form=form)


@case_tasks_blueprint.route('/case/tasks/list', methods=['GET'])
@api_login_required
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
@api_login_required
def case_get_tasks_state(caseid):
    os = get_tasks_state(caseid=caseid)
    if os:
        return response_success(data=os)
    else:
        return response_error('No tasks state for this case.')


@case_tasks_blueprint.route('/case/tasks/status/update/<int:cur_id>', methods=['POST'])
@api_login_required
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
@login_required
def case_add_task_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_tasks.case_tasks', cid=caseid))

    task = CaseTasks()

    form = CaseTaskForm()
    form.task_assignee_id.choices = [(user.id, user.name) for user in
                                     User.query.filter(User.active == True).order_by(User.name).all()]
    form.task_status.choices = [(a.id, a.status_name) for a in get_tasks_status()]

    return render_template("modal_add_case_task.html", form=form, task=task, uid=current_user.id, user_name=None)


@case_tasks_blueprint.route('/case/tasks/add', methods=['POST'])
@api_login_required
def case_add_task(caseid):

    try:
        # validate before saving
        task_schema = CaseTaskSchema()
        jsdata = request.get_json()
        task = task_schema.load(jsdata)

        ctask = add_task(task=task,
                         user_id=current_user.id,
                         caseid=caseid
                         )

        if ctask:
            track_activity("added task {}".format(ctask.task_title), caseid=caseid)
            return response_success(data=task_schema.dump(ctask))

        return response_error("Unable to create task for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@case_tasks_blueprint.route('/case/tasks/<int:cur_id>', methods=['GET'])
@api_login_required
def case_task_view(cur_id, caseid):
    task = get_task(task_id=cur_id, caseid=caseid)
    if not task:
        return response_error("Invalid task ID for this case")

    task_schema = CaseTaskSchema()

    return response_success(data=task_schema.dump(task))


@case_tasks_blueprint.route('/case/tasks/<int:cur_id>/modal', methods=['GET'])
@login_required
def case_task_view_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_tasks.case_tasks', cid=caseid))

    form = CaseTaskForm()
    task = get_task(task_id=cur_id, caseid=caseid)
    form.task_assignee_id.choices = [(user.id, user.name) for user in
                                     User.query.filter(User.active == True).order_by(User.name).all()]
    form.task_status.choices = [(a.id, a.status_name) for a in get_tasks_status()]

    if not task:
        return response_error("Invalid task ID for this case")

    form.task_title.render_kw = {'value': task.task_title}
    form.task_description.data = task.task_description
    user_name, = User.query.with_entities(User.name).filter(User.id == task.task_userid_update).first()

    return render_template("modal_add_case_task.html", form=form, task=task,
                           uid=task.task_assignee_id, user_name=user_name)


@case_tasks_blueprint.route('/case/tasks/update/<int:cur_id>', methods=['POST'])
@api_login_required
def case_edit_task(cur_id, caseid):

    try:
        task = get_task(task_id=cur_id, caseid=caseid)
        if not task:
            return response_error("Invalid task ID for this case")

        # validate before saving
        task_schema = CaseTaskSchema()
        jsdata = request.get_json()
        task = task_schema.load(jsdata, instance=task)

        task.task_userid_update = current_user.id
        task.task_last_update = datetime.utcnow()

        update_tasks_state(caseid=caseid)

        db.session.commit()

        if task:
            track_activity("updated task {} (status {})".format(task.task_title, task.task_status), caseid=caseid)
            return response_success(data=task_schema.dump(task))

        return response_error("Unable to update task for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages, status=400)


@case_tasks_blueprint.route('/case/tasks/delete/<int:cur_id>', methods=['GET'])
@api_login_required
def case_edit_delete(cur_id, caseid):
    task = get_task(task_id=cur_id, caseid=caseid)
    if not task:
        return response_error("Invalid task ID for this case")

    CaseTasks.query.filter(CaseTasks.id == cur_id, CaseTasks.task_case_id == caseid).delete()

    update_tasks_state(caseid=caseid)
    track_activity("deleted task ID {}".format(cur_id))

    return response_success("Task deleted")

