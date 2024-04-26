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

from flask import Blueprint

from app.models.models import TaskStatus
from app.util import ac_api_requires
from app.util import response_error
from app.util import response_success

manage_task_status_blueprint = Blueprint('manage_task_status', __name__, template_folder='templates')


@manage_task_status_blueprint.route('/manage/task-status/list', methods=['GET'])
@ac_api_requires()
def list_task_status():
    lstatus = TaskStatus.query.with_entities(
        TaskStatus.id,
        TaskStatus.status_name,
        TaskStatus.status_bscolor,
        TaskStatus.status_description
    ).all()

    data = [row._asdict() for row in lstatus]

    return response_success("", data=data)


# CONTENT ------------------------------------------------
@manage_task_status_blueprint.route('/manage/task-status/<int:cur_id>', methods=['GET'])
@ac_api_requires()
def view_task_status(cur_id):
    lstatus = TaskStatus.query.with_entities(
        TaskStatus.id,
        TaskStatus.status_name,
        TaskStatus.status_bscolor,
        TaskStatus.status_description
    ).filter(
        TaskStatus.id == cur_id
    ).first()

    if not lstatus:
        return response_error(f"Task status ID #{cur_id} not found")

    return response_success(data=lstatus._asdict())
