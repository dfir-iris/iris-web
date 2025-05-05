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
from app.models.models import CaseResponse
from app.models.authorization import User
from app.schema.marshables import CaseResponseSchema


def get_case_responses_list_by_case_id(case_id: int) -> List[dict]:
    """Get a list of case responses filtered by case_id.

    Args:
        case_id (int): The ID of the case for which to fetch responses.

    Returns:
        List[dict]: List of case responses associated with the specified case_id.
    """
    case_response = CaseResponse.query.with_entities(
        CaseResponse.id,
        CaseResponse.created_at,
        CaseResponse.updated_at,
        CaseResponse.case,
        CaseResponse.trigger,
        CaseResponse.body,
        User.name.label('created_by')
    ).filter(CaseResponse.case == case_id).all()  # Filter responses by case_id

    return [row._asdict() for row in case_response]



def get_case_response_by_id(response_id: int) -> CaseResponse:
    """Get a specific case response by ID.

    Args:
        response_id (int): Task response ID.

    Returns:
        CaseResponse: Task response object.
    """
    case_response = CaseResponse.query.filter_by(id=response_id)
    return case_response


def delete_case_response_by_id(response_id: int):
    """Delete a specific case response by ID.

    Args:
        response_id (int): Task response ID.
    """
    CaseResponse.query.filter_by(id=response_id).delete()


def validate_case_response(data: dict, update: bool = False) -> Optional[str]:
    """Validate case response data.

    Args:
        data (dict): The data to validate.
        update (bool): Whether this is an update operation. Defaults to False.

    Returns:
        Optional[str]: Validation error message, or None if validation passes.
    """
    try:
        if not update:
            # Check required fields for creation
            if "case" not in data:
                return "Task ID is required."

        # Check if trigger is provided and valid
        if "trigger" in data and not isinstance(data["trigger"], int):
            return "Action must be an integer."

        # Validate the body field if provided
        if "body" in data:
            if not isinstance(data["body"], dict):
                return "Body must be a dictionary."
        
        # If all validations pass, return None
        return None
    except Exception as e:
        return str(e)

