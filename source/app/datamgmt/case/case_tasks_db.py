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

from datetime import datetime
from flask_login import current_user
from sqlalchemy import desc, and_

from app import db
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.manage.manage_users_db import get_users_list_restricted_from_case
from app.datamgmt.states import update_tasks_state
from app.models import CaseTasks, TaskAssignee
from app.models import Cases
from app.models import Comments
from app.models import TaskComments
from app.models import TaskStatus
from app.models.authorization import User


def get_tasks_status():
    return TaskStatus.query.all()


def get_tasks(caseid):
    return CaseTasks.query.with_entities(
        CaseTasks.id.label("task_id"),
        CaseTasks.task_uuid,
        CaseTasks.task_title,
        CaseTasks.task_description,
        CaseTasks.task_open_date,
        CaseTasks.task_tags,
        CaseTasks.task_status_id,
        TaskStatus.status_name,
        TaskStatus.status_bscolor
    ).filter(
        CaseTasks.task_case_id == caseid
    ).join(
        CaseTasks.status
    ).order_by(
        desc(TaskStatus.status_name)
    ).all()


def get_tasks_with_assignees(caseid):
    tasks = get_tasks(caseid)
    if not tasks:
        return None

    tasks = [c._asdict() for c in tasks]

    task_with_assignees = []
    for task in tasks:
        task_id = task['task_id']
        get_assignee_list = TaskAssignee.query.with_entities(
            TaskAssignee.task_id,
            User.user,
            User.id,
            User.name
        ).join(
            TaskAssignee.user
        ).filter(
            TaskAssignee.task_id == task_id
        ).all()

        assignee_list = {}
        for member in get_assignee_list:
            if member.task_id not in assignee_list:

                assignee_list[member.task_id] = [{
                    'user': member.user,
                    'name': member.name,
                    'id': member.id
                }]
            else:
                assignee_list[member.task_id].append({
                    'user': member.user,
                    'name': member.name,
                    'id': member.id
                })
        task['task_assignees'] = assignee_list.get(task['task_id'], [])
        task_with_assignees.append(task)

    return task_with_assignees


def get_task(task_id, caseid):
    return CaseTasks.query.filter(CaseTasks.id == task_id, CaseTasks.task_case_id == caseid).first()


def get_task_with_assignees(task_id: int, case_id: int):
    """
    Returns a task with its assignees

    Args:
        task_id (int): Task ID
        case_id (int): Case ID

    Returns:
        dict: Task with its assignees
    """
    task = get_task(
        task_id=task_id,
        caseid=case_id
    )

    if not task:
        return None

    get_assignee_list = TaskAssignee.query.with_entities(
        TaskAssignee.task_id,
        User.user,
        User.id,
        User.name
    ).join(
        TaskAssignee.user
    ).filter(
        TaskAssignee.task_id == task_id
    ).all()

    assignee_list = {}
    for member in get_assignee_list:
        if member.task_id not in assignee_list:

            assignee_list[member.task_id] = [{
                'user': member.user,
                'name': member.name,
                'id': member.id
            }]
        else:
            assignee_list[member.task_id].append({
                'user': member.user,
                'name': member.name,
                'id': member.id
            })

    setattr(task, 'task_assignees', assignee_list.get(task.id, []))

    return task


def update_task_status(task_status, task_id, caseid):
    task = get_task(task_id, caseid)
    if task:
        try:
            task.task_status_id = task_status

            update_tasks_state(caseid=caseid)
            db.session.commit()
            return True

        except:
            return False
    else:
        return False


def update_task_assignees(task, task_assignee_list, caseid):
    if not task:
        return None

    cur_assignee_list = TaskAssignee.query.with_entities(
        TaskAssignee.user_id
    ).filter(TaskAssignee.task_id == task.id).all()

    # Some formatting
    set_cur_assignees = set([assignee[0] for assignee in cur_assignee_list])
    set_assignees = set(int(assignee) for assignee in task_assignee_list)

    assignees_to_add = set_assignees - set_cur_assignees
    assignees_to_remove = set_cur_assignees - set_assignees

    allowed_users = [u.get('user_id') for u in get_users_list_restricted_from_case(caseid)]

    for uid in assignees_to_add:
        if uid not in allowed_users:
            continue

        user = User.query.filter(User.id == uid).first()
        if user:
            ta = TaskAssignee()
            ta.task_id = task.id
            ta.user_id = user.id
            db.session.add(ta)

    for uid in assignees_to_remove:
        TaskAssignee.query.filter(
            and_(TaskAssignee.task_id == task.id,
                 TaskAssignee.user_id == uid)
        ).delete()

    db.session.commit()

    return task


def add_task(task, assignee_id_list, user_id, caseid):
    now = datetime.now()
    task.task_case_id = caseid
    task.task_userid_open = user_id
    task.task_userid_update = user_id
    task.task_open_date = now
    task.task_last_update = now

    task.custom_attributes = task.custom_attributes if task.custom_attributes else get_default_custom_attributes('task')

    db.session.add(task)

    update_tasks_state(caseid=caseid)
    db.session.commit()

    update_task_status(task.task_status_id, task.id, caseid)
    update_task_assignees(task, assignee_id_list, caseid)

    return task


def get_case_task_comments(task_id):
    return Comments.query.filter(
        TaskComments.comment_task_id == task_id
    ).join(
        TaskComments,
        Comments.comment_id == TaskComments.comment_id
    ).order_by(
        Comments.comment_date.asc()
    ).all()


def add_comment_to_task(task_id, comment_id):
    ec = TaskComments()
    ec.comment_task_id = task_id
    ec.comment_id = comment_id

    db.session.add(ec)
    db.session.commit()


def get_case_tasks_comments_count(tasks_list):
    return TaskComments.query.filter(
        TaskComments.comment_task_id.in_(tasks_list)
    ).with_entities(
        TaskComments.comment_task_id,
        TaskComments.comment_id
    ).group_by(
        TaskComments.comment_task_id,
        TaskComments.comment_id
    ).all()


def get_case_task_comment(task_id, comment_id):
    return TaskComments.query.filter(
        TaskComments.comment_task_id == task_id,
        TaskComments.comment_id == comment_id
    ).with_entities(
        Comments.comment_id,
        Comments.comment_text,
        Comments.comment_date,
        Comments.comment_update_date,
        Comments.comment_uuid,
        User.name,
        User.user
    ).join(
        TaskComments.comment
    ).join(
        Comments.user
    ).first()


def delete_task(task_id):
    with db.session.begin_nested():
        TaskAssignee.query.filter(
            TaskAssignee.task_id == task_id
        ).delete()

        com_ids = TaskComments.query.with_entities(
            TaskComments.comment_id
        ).filter(
            TaskComments.comment_task_id == task_id
        ).all()

        com_ids = [c.comment_id for c in com_ids]
        TaskComments.query.filter(TaskComments.comment_id.in_(com_ids)).delete()

        Comments.query.filter(Comments.comment_id.in_(com_ids)).delete()

        CaseTasks.query.filter(
            CaseTasks.id == task_id
        ).delete()


def delete_task_comment(task_id, comment_id):
    comment = Comments.query.filter(
        Comments.comment_id == comment_id,
        Comments.comment_user_id == current_user.id
    ).first()
    if not comment:
        return False, "You are not allowed to delete this comment"

    TaskComments.query.filter(
        TaskComments.comment_task_id == task_id,
        TaskComments.comment_id == comment_id
    ).delete()

    db.session.delete(comment)
    db.session.commit()

    return True, "Comment deleted"


def get_tasks_cases_mapping(open_cases_only=False):
    condition = Cases.close_date == None if open_cases_only else True

    return CaseTasks.query.filter(
        condition
    ).with_entities(
        CaseTasks.task_case_id,
        CaseTasks.task_status_id
    ).join(
        CaseTasks.case
    ).all()
