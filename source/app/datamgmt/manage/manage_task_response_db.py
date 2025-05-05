#  IRIS Source Code
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

from datetime import datetime
from typing import List, Optional, Union

from app import db
from app.models.models import TaskResponse
from app.models.authorization import User
from app.schema.marshables import TaskResponseSchema


def get_task_responses_list(task_id: int) -> List[dict]:
    """Get a list of task responses.

    Returns:
        List[dict]: List of task responses.
    """
    task_responses = TaskResponse.query.with_entities(
        TaskResponse.id,
        TaskResponse.created_at,
        TaskResponse.updated_at,
        TaskResponse.task,
        TaskResponse.action,
        TaskResponse.body,
        User.name.label('created_by')).filter(TaskResponse.task == task_id).all()

    return [row._asdict() for row in task_responses]


def get_task_response_by_id(response_id: int) -> TaskResponse:
    """Get a specific task response by ID.

    Args:
        response_id (int): Task response ID.

    Returns:
        TaskResponse: Task response object.
    """
    task_response = TaskResponse.query.filter_by(id=response_id).first()
    print("in here")
    return task_response


def delete_task_response_by_id(response_id: int):
    """Delete a specific task response by ID.

    Args:
        response_id (int): Task response ID.
    """
    TaskResponse.query.filter_by(id=response_id).delete()


def validate_task_response(data: dict, update: bool = False) -> Optional[str]:
    """Validate task response data.

    Args:
        data (dict): The data to validate.
        update (bool): Whether this is an update operation. Defaults to False.

    Returns:
        Optional[str]: Validation error message, or None if validation passes.
    """
    try:
        if not update:
            # Check required fields for creation
            if "task" not in data:
                return "Task ID is required."

        # Check if action is provided and valid
        if "action" in data and not isinstance(data["action"], int):
            return "Action must be an integer."

        # Validate the body field if provided
        if "body" in data:
            if not isinstance(data["body"], dict):
                return "Body must be a dictionary."
        
        # If all validations pass, return None
        return None
    except Exception as e:
        return str(e)
