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
from flask_login import current_user
from flask_wtf import FlaskForm

from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_tasks_db import get_case_tasks_comments_count
from app.datamgmt.case.case_tasks_db import get_task
from app.datamgmt.case.case_tasks_db import get_task_assignees
from app.datamgmt.case.case_tasks_db import get_tasks_status
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.forms import CaseTaskForm
from app.models.authorization import CaseAccessLevel
from app.models.authorization import User
from app.models.models import CaseTasks
from app.blueprints.access_controls import ac_case_requires
from app.blueprints.responses import response_error

case_tasks_blueprint = Blueprint('case_tasks',
                                 __name__,
                                 template_folder='templates')


@case_tasks_blueprint.route('/case/tasks', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_tasks(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_tasks.case_tasks', cid=caseid, redirect=True))

    form = FlaskForm()
    case = get_case(caseid)

    return render_template("case_tasks.html", case=case, form=form)


@case_tasks_blueprint.route('/case/tasks/add/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.full_access)
def case_add_task_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_tasks.case_tasks', cid=caseid, redirect=True))

    task = CaseTasks()
    task.custom_attributes = get_default_custom_attributes('task')
    form = CaseTaskForm()
    form.task_status_id.choices = [(a.id, a.status_name) for a in get_tasks_status()]
    form.task_assignees_id.choices = []

    return render_template("modal_add_case_task.html", form=form, task=task, uid=current_user.id, user_name=None,
                           attributes=task.custom_attributes)


@case_tasks_blueprint.route('/case/tasks/<int:cur_id>/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_task_view_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_tasks.case_tasks', cid=caseid, redirect=True))

    form = CaseTaskForm()

    task = get_task(task_id=cur_id)
    task_assignees = get_task_assignees(cur_id)
    form.task_status_id.choices = [(a.id, a.status_name) for a in get_tasks_status()]
    form.task_assignees_id.choices = []

    if not task:
        return response_error("Invalid task ID for this case")

    form.task_title.render_kw = {'value': task.task_title}
    form.task_description.data = task.task_description
    user_name, = User.query.with_entities(User.name).filter(User.id == task.task_userid_update).first()
    comments_map = get_case_tasks_comments_count([task.id])

    return render_template("modal_add_case_task.html", form=form, task=task, task_assignees=task_assignees,
                           user_name=user_name, comments_map=comments_map, attributes=task.custom_attributes)


@case_tasks_blueprint.route('/case/tasks/<int:cur_id>/comments/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_task_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_task.case_task', cid=caseid, redirect=True))

    task = get_task(cur_id)
    if not task:
        return response_error('Invalid task ID')

    return render_template("modal_conversation.html", element_id=cur_id, element_type='tasks',
                           title=task.task_title)
