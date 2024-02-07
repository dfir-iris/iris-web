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
from typing import List

from app.models.cases import CaseState
from app.schema.marshables import CaseStateSchema


def get_case_states_list() -> List[dict]:
    """Get a list of case state

    Returns:
        List[dict]: List of case state
    """
    case_state = CaseState.query.all()

    return CaseStateSchema(many=True).dump(case_state)


def get_case_state_by_id(cur_id: int) -> CaseState:
    """Get a case state

    Args:
        cur_id (int): case state id

    Returns:
        CaseState: Case state
    """
    case_state = CaseState.query.filter_by(state_id=cur_id).first()
    return case_state


def get_case_state_by_name(cur_name: str) -> CaseState:
    """Get a case state

    Args:
        cur_name (str): case state name

    Returns:
        CaseState: Case state
    """
    case_state = CaseState.query.filter_by(state_name=cur_name).first()
    return case_state


def get_cases_using_state(cur_id: int) -> List[dict]:
    """Get a list of cases using a case state

    Args:
        cur_id (int): case state id

    Returns:
        List[dict]: List of cases
    """
    case_state = get_case_state_by_id(cur_id)
    return case_state.cases
