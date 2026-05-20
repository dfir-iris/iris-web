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
from flask import redirect
from flask import render_template
from flask import url_for
from flask_wtf import FlaskForm
from werkzeug import Response

from app.blueprints.iris_user import iris_current_user
from app.datamgmt.case.case_db import get_case
from app.datamgmt.client.client_db import get_client_list
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.manage.manage_case_classifications_db import get_case_classifications_list
from app.datamgmt.manage.manage_case_state_db import get_case_states_list
from app.datamgmt.manage.manage_case_templates_db import get_case_templates_list
from app.datamgmt.manage.manage_cases_db import get_case_protagonists
from app.datamgmt.manage.manage_common import get_severities_list
from app.forms import AddCaseForm
from app.models.authorization import CaseAccessLevel
from app.models.authorization import Permissions
from app.schema.marshables import CaseDetailsSchema
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.access_controls import ac_current_user_has_permission
from app.blueprints.access_controls import ac_requires
from app.blueprints.responses import response_error
from app.schema.marshables import CaseStateSchema

manage_cases_blueprint = Blueprint('manage_case',
                                   __name__,
                                   template_folder='templates')


@manage_cases_blueprint.route('/manage/cases', methods=['GET'])
@ac_requires(Permissions.standard_user, no_cid_required=True)
def manage_index_cases(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_case.manage_index_cases', cid=caseid))

    return render_template('manage_cases.html')


def _details_case(cur_id: int, caseid: int, url_redir: bool) -> Union[str, Response]:
    """
    Get case details

    Args:
        cur_id (int): case id
        caseid (int): case id
        url_redir (bool): url redirection

    Returns:
        Union[str, Response]: The case details
    """
    if url_redir:
        return response_error("Invalid request")

    if not ac_fast_check_current_user_has_case_access(cur_id, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=cur_id)

    res = get_case(cur_id)
    res = CaseDetailsSchema().dump(res)
    if not res:
        return response_error("Unknown case")

    case_classifications = get_case_classifications_list()
    case_states = get_case_states_list()
    dumped_case_states = CaseStateSchema(many=True).dump(case_states)
    user_is_server_administrator = ac_current_user_has_permission(Permissions.server_administrator)

    customers = get_client_list(iris_current_user.id, user_is_server_administrator)

    severities = get_severities_list()
    protagonists = [r._asdict() for r in get_case_protagonists(cur_id)]

    form = FlaskForm()

    return render_template('modal_case_info_from_case.html', data=res, form=form, protagonists=protagonists,
                           case_classifications=case_classifications, case_states=dumped_case_states, customers=customers,
                           severities=severities)


@manage_cases_blueprint.route('/case/details/<int:cur_id>', methods=['GET'])
@ac_requires(no_cid_required=True)
def details_case_from_case_modal(cur_id: int, caseid: int, url_redir: bool) -> Union[str, Response]:
    return _details_case(cur_id, caseid, url_redir)


@manage_cases_blueprint.route('/manage/cases/details/<int:cur_id>', methods=['GET'])
@ac_requires(no_cid_required=True)
def manage_details_case(cur_id: int, caseid: int, url_redir: bool) -> Union[Response, str]:
    return _details_case(cur_id, caseid, url_redir)


@manage_cases_blueprint.route('/manage/cases/add/modal', methods=['GET'])
@ac_requires(Permissions.standard_user)
def add_case_modal(caseid: int, url_redir: bool):
    if url_redir:
        return redirect(url_for('manage_case.manage_index_cases', cid=caseid))

    form = AddCaseForm()

    # Show only clients that the user has access to
    client_list = get_client_list(iris_current_user.id, ac_current_user_has_permission(Permissions.server_administrator))

    form.case_customer_id.choices = [(c['customer_id'], c['customer_name']) for c in client_list]

    form.classification_id.choices = [(clc['id'], clc['name_expanded']) for clc in get_case_classifications_list()]
    form.case_template_id.choices = [(ctp['id'], ctp['display_name']) for ctp in get_case_templates_list()]

    attributes = get_default_custom_attributes('case')

    return render_template('modal_add_case.html', form=form, attributes=attributes)
