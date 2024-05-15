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
import marshmallow
from typing import Union

from flask import Blueprint
from flask import Response
from flask import url_for
from flask import render_template
from flask import request
from werkzeug.utils import redirect

from app import db
from app.datamgmt.manage.manage_case_state_db import get_case_states_list
from app.datamgmt.manage.manage_case_state_db import get_case_state_by_id
from app.datamgmt.manage.manage_case_state_db import get_cases_using_state
from app.forms import CaseStateForm
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.schema.marshables import CaseStateSchema
from app.util import ac_api_requires
from app.util import response_error
from app.util import ac_requires
from app.util import response_success

manage_case_state_blueprint = Blueprint('manage_case_state',
                                        __name__,
                                        template_folder='templates')


# CONTENT ------------------------------------------------
@manage_case_state_blueprint.route('/manage/case-states/list', methods=['GET'])
@ac_api_requires()
def list_case_state() -> Response:
    """Get the list of case state

    Returns:
        Flask Response object

    """
    l_cl = get_case_states_list()

    return response_success("", data=l_cl)


@manage_case_state_blueprint.route('/manage/case-states/<int:state_id>', methods=['GET'])
@ac_api_requires()
def get_case_state(state_id: int) -> Response:
    """Get a case state

    Args:
        state_id (int): case state id

    Returns:
        Flask Response object
    """

    schema = CaseStateSchema()
    case_state = get_case_state_by_id(state_id)
    if not case_state:
        return response_error(f"Invalid case state ID {state_id}")

    return response_success("", data=schema.dump(case_state))


@manage_case_state_blueprint.route('/manage/case-states/update/<int:state_id>/modal',
                                            methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def update_case_state_modal(state_id: int, caseid: int, url_redir: bool) -> Union[str, Response]:
    """Update a case state

    Args:
        state_id (int): case state id
        caseid (int): case id
        url_redir (bool): redirect to url

    Returns:
        Flask Response object or str
    """
    if url_redir:
        return redirect(url_for('manage_case_state_blueprint.update_case_state_modal',
                                state_id=state_id, caseid=caseid))

    state_form = CaseStateForm()
    case_state = get_case_state_by_id(state_id)
    if not case_state:
        return response_error(f"Invalid case state ID {state_id}")

    state_form.state_name.render_kw = {'value': case_state.state_name}
    state_form.state_description.render_kw = {'value': case_state.state_description}

    return render_template("modal_case_state.html", form=state_form,
                           case_state=case_state)


@manage_case_state_blueprint.route('/manage/case-states/update/<int:state_id>',
                                            methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def update_case_state(state_id: int) -> Response:
    """Update a case state

    Args:
        state_id (int): case state id

    Returns:
        Flask Response object
    """
    if not request.is_json:
        return response_error("Invalid request")

    case_state = get_case_state_by_id(state_id)
    if not case_state:
        return response_error(f"Invalid case state ID {state_id}")

    if case_state.protected:
        return response_error(f"Case state {case_state.state_name} is protected")

    ccl = CaseStateSchema()

    try:

        ccls = ccl.load(request.get_json(), instance=case_state)

        if ccls:
            track_activity(f"updated case state {ccls.state_id}")
            return response_success("Case state updated", ccl.dump(ccls))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    return response_error("Unexpected error server-side. Nothing updated", data=case_state)


@manage_case_state_blueprint.route('/manage/case-states/add/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def add_case_state_modal(caseid: int, url_redir: bool) -> Union[str, Response]:
    """Add a case state

    Args:
        caseid (int): case id
        url_redir (bool): redirect to url

    Returns:
        Flask Response object or str
    """
    if url_redir:
        return redirect(url_for('manage_case_state_blueprint.add_case_state_modal',
                                caseid=caseid))

    state_form = CaseStateForm()

    return render_template("modal_case_state.html", form=state_form, case_state=None)


@manage_case_state_blueprint.route('/manage/case-states/add', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def add_case_state() -> Response:
    """Add a case state

    Returns:
        Flask Response object
    """
    if not request.is_json:
        return response_error("Invalid request")

    ccl = CaseStateSchema()

    try:

        ccls = ccl.load(request.get_json())

        if ccls:
            db.session.add(ccls)
            db.session.commit()

            track_activity(f"added case state {ccls.state_name}")
            return response_success("Case state added", ccl.dump(ccls))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    return response_error("Unexpected error server-side. Nothing added", data=None)


@manage_case_state_blueprint.route('/manage/case-states/delete/<int:state_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def delete_case_state(state_id: int) -> Response:
    """Delete a case state

    Args:
        state_id (int): case state id

    Returns:
        Flask Response object
    """
    case_state = get_case_state_by_id(state_id)
    if not case_state:
        return response_error(f"Invalid case state ID {state_id}")

    if case_state.protected:
        return response_error(f"Case state {case_state.state_name} is protected")

    cases = get_cases_using_state(case_state.state_id)
    if cases:
        return response_error(f"Case state {case_state.state_name} is in use by case(s)"
                              f" {','.join([str(c.case_id) for c in cases])}")

    db.session.delete(case_state)
    db.session.commit()

    track_activity(f"deleted case state {case_state.state_name}")
    return response_success("Case state deleted")
