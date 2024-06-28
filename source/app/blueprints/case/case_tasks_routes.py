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

# IMPORTS ------------------------------------------------
from datetime import datetime

import marshmallow
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from flask_wtf import FlaskForm

from app import db
from app.blueprints.case.case_comments import case_comment_update
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_tasks_db import add_comment_to_task
from app.datamgmt.case.case_tasks_db import add_task
from app.datamgmt.case.case_tasks_db import delete_task
from app.datamgmt.case.case_tasks_db import delete_task_comment
from app.datamgmt.case.case_tasks_db import get_case_task_comment
from app.datamgmt.case.case_tasks_db import get_case_task_comments
from app.datamgmt.case.case_tasks_db import get_case_tasks_comments_count
from app.datamgmt.case.case_tasks_db import get_task
from app.datamgmt.case.case_tasks_db import get_task_with_assignees
from app.datamgmt.case.case_tasks_db import get_tasks_status
from app.datamgmt.case.case_tasks_db import get_tasks_with_assignees
from app.datamgmt.case.case_tasks_db import update_task_assignees
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
from app.schema.marshables import CommentSchema
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
    ct = get_tasks_with_assignees(caseid)

    if not ct:
        output = []
    else:
        output = ct

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
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_add_task_modal(caseid):

    task = CaseTasks()
    task.custom_attributes = get_default_custom_attributes('task')
    form = CaseTaskForm()
    form.task_status_id.choices = [(a.id, a.status_name) for a in get_tasks_status()]
    form.task_assignees_id.choices = []

    return render_template("modal_add_case_task.html", form=form, task=task, uid=current_user.id, user_name=None,
                           attributes=task.custom_attributes)


@case_tasks_blueprint.route('/case/tasks/add', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_add_task(caseid):
    try:
        # validate before saving
        task_schema = CaseTaskSchema()
        request_data = call_modules_hook('on_preload_task_create', data=request.get_json(), caseid=caseid)

        if 'task_assignee_id' in request_data or 'task_assignees_id' not in request_data:
            return response_error('task_assignee_id is not valid anymore since v1.5.0')

        task_assignee_list = request_data['task_assignees_id']
        del request_data['task_assignees_id']
        task = task_schema.load(request_data)

        ctask = add_task(task=task,
                         assignee_id_list=task_assignee_list,
                         user_id=current_user.id,
                         caseid=caseid
                         )

        ctask = call_modules_hook('on_postload_task_create', data=ctask, caseid=caseid)

        if ctask:
            track_activity(f"added task \"{ctask.task_title}\"", caseid=caseid)
            return response_success("Task '{}' added".format(ctask.task_title), data=task_schema.dump(ctask))

        return response_error("Unable to create task for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@case_tasks_blueprint.route('/case/tasks/<int:cur_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_task_view(cur_id, caseid):
    task = get_task_with_assignees(task_id=cur_id, case_id=caseid)
    if not task:
        return response_error("Invalid task ID for this case")

    task_schema = CaseTaskSchema()

    return response_success(data=task_schema.dump(task))


@case_tasks_blueprint.route('/case/tasks/<int:cur_id>/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_task_view_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_tasks.case_tasks', cid=caseid, redirect=True))

    form = CaseTaskForm()

    task = get_task_with_assignees(task_id=cur_id, case_id=caseid)
    form.task_status_id.choices = [(a.id, a.status_name) for a in get_tasks_status()]
    form.task_assignees_id.choices = []

    if not task:
        return response_error("Invalid task ID for this case")

    form.task_title.render_kw = {'value': task.task_title}
    form.task_description.data = task.task_description
    user_name, = User.query.with_entities(User.name).filter(User.id == task.task_userid_update).first()
    comments_map = get_case_tasks_comments_count([task.id])

    return render_template("modal_add_case_task.html", form=form, task=task, user_name=user_name,
                           comments_map=comments_map, attributes=task.custom_attributes)


@case_tasks_blueprint.route('/case/tasks/update/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_edit_task(cur_id, caseid):
    try:
        task = get_task_with_assignees(task_id=cur_id, case_id=caseid)
        if not task:
            return response_error("Invalid task ID for this case")

        request_data = call_modules_hook('on_preload_task_update', data=request.get_json(), caseid=caseid)

        if 'task_assignee_id' in request_data or 'task_assignees_id' not in request_data:
            return response_error('task_assignee_id is not valid anymore since v1.5.0')

        # validate before saving
        task_assignee_list = request_data['task_assignees_id']
        del request_data['task_assignees_id']
        task_schema = CaseTaskSchema()

        request_data['id'] = cur_id
        task = task_schema.load(request_data, instance=task)

        task.task_userid_update = current_user.id
        task.task_last_update = datetime.utcnow()

        update_task_assignees(task, task_assignee_list, caseid)

        update_tasks_state(caseid=caseid)

        db.session.commit()

        task = call_modules_hook('on_postload_task_update', data=task, caseid=caseid)

        if task:
            track_activity(f"updated task \"{task.task_title}\" (status {task.status.status_name})",
                           caseid=caseid)
            return response_success("Task '{}' updated".format(task.task_title), data=task_schema.dump(task))

        return response_error("Unable to update task for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@case_tasks_blueprint.route('/case/tasks/delete/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_delete_task(cur_id, caseid):
    call_modules_hook('on_preload_task_delete', data=cur_id, caseid=caseid)
    task = get_task_with_assignees(task_id=cur_id, case_id=caseid)
    if not task:
        return response_error("Invalid task ID for this case")

    delete_task(task.id)

    update_tasks_state(caseid=caseid)

    call_modules_hook('on_postload_task_delete', data=cur_id, caseid=caseid)

    track_activity(f"deleted task \"{task.task_title}\"")

    return response_success("Task deleted")


@case_tasks_blueprint.route('/case/tasks/<int:cur_id>/comments/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_task_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_task.case_task', cid=caseid, redirect=True))

    task = get_task(cur_id, caseid=caseid)
    if not task:
        return response_error('Invalid task ID')

    return render_template("modal_conversation.html", element_id=cur_id, element_type='tasks',
                           title=task.task_title)


@case_tasks_blueprint.route('/case/tasks/<int:cur_id>/comments/list', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_task_list(cur_id, caseid):

    task_comments = get_case_task_comments(cur_id)
    if task_comments is None:
        return response_error('Invalid task ID')

    return response_success(data=CommentSchema(many=True).dump(task_comments))


@case_tasks_blueprint.route('/case/tasks/<int:cur_id>/comments/add', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_task_add(cur_id, caseid):

    try:
        task = get_task(cur_id, caseid=caseid)
        if not task:
            return response_error('Invalid task ID')

        comment_schema = CommentSchema()

        comment = comment_schema.load(request.get_json())
        comment.comment_case_id = caseid
        comment.comment_user_id = current_user.id
        comment.comment_date = datetime.now()
        comment.comment_update_date = datetime.now()
        db.session.add(comment)
        db.session.commit()

        add_comment_to_task(task.id, comment.comment_id)

        db.session.commit()

        hook_data = {
            "comment": comment_schema.dump(comment),
            "task": CaseTaskSchema().dump(task)
        }
        call_modules_hook('on_postload_task_commented', data=hook_data, caseid=caseid)

        track_activity(f"task \"{task.task_title}\" commented", caseid=caseid)
        return response_success("Task commented", data=comment_schema.dump(comment))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages())


@case_tasks_blueprint.route('/case/tasks/<int:cur_id>/comments/<int:com_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_task_get(cur_id, com_id, caseid):

    comment = get_case_task_comment(cur_id, com_id)
    if not comment:
        return response_error("Invalid comment ID")

    return response_success(data=comment._asdict())


@case_tasks_blueprint.route('/case/tasks/<int:cur_id>/comments/<int:com_id>/edit', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_task_edit(cur_id, com_id, caseid):

    return case_comment_update(com_id, 'tasks', caseid)


@case_tasks_blueprint.route('/case/tasks/<int:cur_id>/comments/<int:com_id>/delete', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def case_comment_task_delete(cur_id, com_id, caseid):

    success, msg = delete_task_comment(cur_id, com_id)
    if not success:
        return response_error(msg)

    call_modules_hook('on_postload_task_comment_delete', data=com_id, caseid=caseid)

    track_activity(f"comment {com_id} on task {cur_id} deleted", caseid=caseid)
    return response_success(msg)

