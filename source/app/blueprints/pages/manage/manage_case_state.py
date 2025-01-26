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

from typing import Union

from flask import Blueprint
from flask import Response
from flask import url_for
from flask import render_template
from werkzeug.utils import redirect

from app.datamgmt.manage.manage_case_state_db import get_case_state_by_id
from app.forms import CaseStateForm
from app.models.authorization import Permissions
from app.blueprints.responses import response_error
from app.blueprints.access_controls import ac_requires

manage_case_state_blueprint = Blueprint('manage_case_state',
                                        __name__,
                                        template_folder='templates')


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
