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
import logging as log
import os
import traceback
import urllib.parse

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from flask_wtf import FlaskForm
from werkzeug import Response
from werkzeug.utils import secure_filename

from app import db
from app.datamgmt.alerts.alerts_db import get_alert_status_by_name
from app.datamgmt.case.case_db import get_case
from app.datamgmt.client.client_db import get_client_list
from app.datamgmt.iris_engine.modules_db import get_pipelines_args_from_name
from app.datamgmt.iris_engine.modules_db import iris_module_exists
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.manage.manage_case_classifications_db import get_case_classifications_list
from app.datamgmt.manage.manage_case_state_db import get_case_states_list
from app.datamgmt.manage.manage_case_templates_db import get_case_templates_list
from app.datamgmt.manage.manage_cases_db import get_filtered_cases
from app.datamgmt.manage.manage_cases_db import close_case, map_alert_resolution_to_case_status
from app.datamgmt.manage.manage_cases_db import get_case_details_rt
from app.datamgmt.manage.manage_cases_db import get_case_protagonists
from app.datamgmt.manage.manage_cases_db import list_cases_dict
from app.datamgmt.manage.manage_cases_db import reopen_case
from app.datamgmt.manage.manage_common import get_severities_list
from app.forms import AddCaseForm
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.iris_engine.access_control.utils import ac_current_user_has_permission
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.module_handler.module_handler import configure_module_on_init
from app.iris_engine.module_handler.module_handler import instantiate_module_from_name
from app.iris_engine.tasker.tasks import task_case_update
from app.iris_engine.utils.common import build_upload_path
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.models.authorization import Permissions
from app.schema.marshables import CaseSchema
from app.schema.marshables import CaseDetailsSchema
from app.util import add_obj_history_entry
from app.util import ac_api_requires
from app.util import ac_requires_case_identifier
from app.util import ac_api_return_access_denied
from app.util import ac_requires
from app.util import response_error
from app.util import response_success
from app.business.cases import delete
from app.business.cases import update
from app.business.cases import create
from app.business.errors import BusinessProcessingError
from app.business.errors import PermissionDeniedError

manage_cases_blueprint = Blueprint('manage_case',
                                   __name__,
                                   template_folder='templates')


# CONTENT ------------------------------------------------
@manage_cases_blueprint.route('/manage/cases', methods=['GET'])
@ac_requires(Permissions.standard_user, no_cid_required=True)
def manage_index_cases(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_case.manage_index_cases', cid=caseid))

    return render_template('manage_cases.html')


def details_case(cur_id: int, caseid: int, url_redir: bool) -> Union[str, Response]:
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
    case_classifications = get_case_classifications_list()
    case_states = get_case_states_list()
    user_is_server_administrator = ac_current_user_has_permission(Permissions.server_administrator)

    customers = get_client_list(current_user_id=current_user.id,
                                is_server_administrator=user_is_server_administrator)

    severities = get_severities_list()
    protagonists = [r._asdict() for r in get_case_protagonists(cur_id)]

    form = FlaskForm()

    if res:
        print(res.get('status_name'))
        return render_template("modal_case_info_from_case.html", data=res, form=form, protagonists=protagonists,
                               case_classifications=case_classifications, case_states=case_states, customers=customers,
                               severities=severities)

    else:
        return response_error("Unknown case")


@manage_cases_blueprint.route('/case/details/<int:cur_id>', methods=['GET'])
@ac_requires(no_cid_required=True)
def details_case_from_case_modal(cur_id: int, caseid: int, url_redir: bool) -> Union[str, Response]:
    return details_case(cur_id, caseid, url_redir)


@manage_cases_blueprint.route('/manage/cases/details/<int:cur_id>', methods=['GET'])
@ac_requires(no_cid_required=True)
def manage_details_case(cur_id: int, caseid: int, url_redir: bool) -> Union[Response, str]:
    return details_case(cur_id, caseid, url_redir)


@manage_cases_blueprint.route('/manage/cases/<int:cur_id>', methods=['GET'])
@ac_api_requires()
def get_case_api(cur_id):
    if not ac_fast_check_current_user_has_case_access(cur_id, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=cur_id)

    res = get_case_details_rt(cur_id)
    if res:
        return response_success(data=res)

    return response_error(f'Case ID {cur_id} not found')


@manage_cases_blueprint.route('/manage/cases/filter', methods=['GET'])
@ac_api_requires()
def manage_case_filter() -> Response:

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    case_ids_str = request.args.get('case_ids', None, type=str)
    order_by = request.args.get('order_by', type=str)
    sort_dir = request.args.get('sort_dir', 'asc', type=str)

    if case_ids_str:
        try:

            if ',' in case_ids_str:
                case_ids_str = [int(alert_id) for alert_id in case_ids_str.split(',')]

            else:
                case_ids_str = [int(case_ids_str)]

        except ValueError:
            return response_error('Invalid case id')

    case_customer_id = request.args.get('case_customer_id', None, type=str)
    case_name = request.args.get('case_name', None, type=str)
    case_description = request.args.get('case_description', None, type=str)
    case_classification_id = request.args.get('case_classification_id', None, type=int)
    case_owner_id = request.args.get('case_owner_id', None, type=int)
    case_opening_user_id = request.args.get('case_opening_user_id', None, type=int)
    case_severity_id = request.args.get('case_severity_id', None, type=int)
    case_state_id = request.args.get('case_state_id', None, type=int)
    case_soc_id = request.args.get('case_soc_id', None, type=str)
    start_open_date = request.args.get('start_open_date', None, type=str)
    end_open_date = request.args.get('end_open_date', None, type=str)
    draw = request.args.get('draw', 1, type=int)
    search_value = request.args.get('search[value]', type=str)  # Get the search value from the request

    if type(draw) is not int:
        draw = 1

    filtered_cases = get_filtered_cases(
        case_ids=case_ids_str,
        case_customer_id=case_customer_id,
        case_name=case_name,
        case_description=case_description,
        case_classification_id=case_classification_id,
        case_owner_id=case_owner_id,
        case_opening_user_id=case_opening_user_id,
        case_severity_id=case_severity_id,
        case_state_id=case_state_id,
        case_soc_id=case_soc_id,
        start_open_date=start_open_date,
        end_open_date=end_open_date,
        search_value=search_value,
        page=page,
        per_page=per_page,
        current_user_id=current_user.id,
        sort_by=order_by,
        sort_dir=sort_dir
    )
    if filtered_cases is None:
        return response_error('Filtering error')

    cases = {
        'total': filtered_cases.total,
        'cases': CaseDetailsSchema().dump(filtered_cases.items, many=True),
        'last_page': filtered_cases.pages,
        'current_page': filtered_cases.page,
        'next_page': filtered_cases.next_num if filtered_cases.has_next else None,
        'draw': draw
    }

    return response_success(data=cases)


@manage_cases_blueprint.route('/manage/cases/delete/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.standard_user)
def api_delete_case(cur_id):
    try:
        delete(cur_id)
        return response_success('Case successfully deleted')
    except BusinessProcessingError as e:
        return response_error(e.get_message())
    except PermissionDeniedError:
        return ac_api_return_access_denied(caseid=cur_id)


@manage_cases_blueprint.route('/manage/cases/reopen/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.standard_user)
def api_reopen_case(cur_id):
    if not ac_fast_check_current_user_has_case_access(cur_id, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=cur_id)

    if not cur_id:
        return response_error("No case ID provided")

    case = get_case(cur_id)
    if not case:
        return response_error("Tried to reopen an non-existing case")

    res = reopen_case(cur_id)
    if not res:
        return response_error("Tried to reopen an non-existing case")

    # Reopen the related alerts
    if case.alerts:
        merged_status = get_alert_status_by_name('Merged')
        for alert in case.alerts:
            if alert.alert_status_id != merged_status.status_id:
                alert.alert_status_id = merged_status.status_id
                track_activity(f"alert ID {alert.alert_id} status updated to merged due to case #{cur_id} being reopen",
                               caseid=cur_id, ctx_less=False)

                db.session.add(alert)
    
    case = call_modules_hook('on_postload_case_update', data=case, caseid=cur_id)

    add_obj_history_entry(case, 'case reopen')
    track_activity("reopen case ID {}".format(cur_id), caseid=cur_id)
    case_schema = CaseSchema()

    return response_success("Case reopen successfully", data=case_schema.dump(res))


@manage_cases_blueprint.route('/manage/cases/close/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.standard_user)
def api_case_close(cur_id):
    if not ac_fast_check_current_user_has_case_access(cur_id, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=cur_id)

    if not cur_id:
        return response_error("No case ID provided")

    case = get_case(cur_id)
    if not case:
        return response_error("Tried to close an non-existing case")

    res = close_case(cur_id)
    if not res:
        return response_error("Tried to close an non-existing case")

    # Close the related alerts
    if case.alerts:
        close_status = get_alert_status_by_name('Closed')
        case_status_id_mapped = map_alert_resolution_to_case_status(case.status_id)

        for alert in case.alerts:
            if alert.alert_status_id != close_status.status_id:
                alert.alert_status_id = close_status.status_id
                alert = call_modules_hook('on_postload_alert_update', data=alert, caseid=cur_id)

            if alert.alert_resolution_status_id != case_status_id_mapped:
                alert.alert_resolution_status_id = case_status_id_mapped
                alert = call_modules_hook('on_postload_alert_resolution_update', data=alert, caseid=cur_id)

                track_activity(f"closing alert ID {alert.alert_id} due to case #{cur_id} being closed",
                               caseid=cur_id, ctx_less=False)

                db.session.add(alert)
    
    case = call_modules_hook('on_postload_case_update', data=case, caseid=cur_id)

    add_obj_history_entry(case, 'case closed')
    track_activity("closed case ID {}".format(cur_id), caseid=cur_id, ctx_less=False)
    case_schema = CaseSchema()

    return response_success("Case closed successfully", data=case_schema.dump(res))


@manage_cases_blueprint.route('/manage/cases/add/modal', methods=['GET'])
@ac_api_requires(Permissions.standard_user)
def add_case_modal():

    form = AddCaseForm()
    # Show only clients that the user has access to
    client_list = get_client_list(current_user_id=current_user.id,
                                  is_server_administrator=ac_current_user_has_permission(
                                     Permissions.server_administrator))

    form.case_customer.choices = [(c['customer_id'], c['customer_name']) for c in client_list]

    form.classification_id.choices = [(clc['id'], clc['name_expanded']) for clc in get_case_classifications_list()]
    form.case_template_id.choices = [(ctp['id'], ctp['display_name']) for ctp in get_case_templates_list()]

    attributes = get_default_custom_attributes('case')

    return render_template('modal_add_case.html', form=form, attributes=attributes)


@manage_cases_blueprint.route('/manage/cases/add', methods=['POST'])
@ac_api_requires(Permissions.standard_user)
def api_add_case():
    case_schema = CaseSchema()

    try:
        case, msg = create(request.get_json())
        return response_success(msg, data=case_schema.dump(case))
    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@manage_cases_blueprint.route('/manage/cases/list', methods=['GET'])
@ac_api_requires(Permissions.standard_user)
def api_list_case():
    data = list_cases_dict(current_user.id)

    return response_success("", data=data)


@manage_cases_blueprint.route('/manage/cases/update/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.standard_user)
def update_case_info(cur_id):
    case_schema = CaseSchema()
    try:
        case, msg = update(cur_id, request.get_json())
        return response_success(msg, data=case_schema.dump(case))
    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@manage_cases_blueprint.route('/manage/cases/trigger-pipeline', methods=['POST'])
@ac_api_requires(Permissions.standard_user)
@ac_requires_case_identifier()
def update_case_files(caseid):
    if not ac_fast_check_current_user_has_case_access(caseid, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=caseid)

    # case update request. The files should have already arrived with the request upload_files
    try:
        # Create the update task
        jsdata = request.get_json()
        if not jsdata:
            return response_error('Not a JSON content')

        pipeline = jsdata.get('pipeline')

        try:
            pipeline_mod = pipeline.split("-")[0]
            pipeline_name = pipeline.split("-")[1]
        except Exception as e:
            log.error(e.__str__())
            return response_error('Malformed request')

        ppl_config = get_pipelines_args_from_name(pipeline_mod)
        if not ppl_config:
            return response_error('Malformed request')

        pl_args = ppl_config['pipeline_args']
        pipeline_args = {}
        for argi in pl_args:

            arg = argi[0]
            fetch_arg = jsdata.get('args_' + arg)

            if argi[1] == 'required' and (not fetch_arg or fetch_arg == ""):
                return response_error("Required arguments are not set")

            if fetch_arg:
                pipeline_args[arg] = fetch_arg

            else:
                pipeline_args[arg] = None

        status = task_case_update(
            module=pipeline_mod,
            pipeline=pipeline_name,
            pipeline_args=pipeline_args,
            caseid=caseid)

        if status.is_success():
            # The job has been created, so return. The progress can be followed on the dashboard
            return response_success("Case task created")

        else:
            # We got some errors and cannot continue
            return response_error(status.get_message(), data=status.get_data())

    except Exception as e:
        traceback.print_exc()
        return response_error('Fail to update case', data=traceback.print_exc())


@manage_cases_blueprint.route('/manage/cases/upload_files', methods=['POST'])
@ac_api_requires(Permissions.standard_user)
@ac_requires_case_identifier()
def manage_cases_uploadfiles(caseid):
    """
    Handles the entire the case management, i.e creation, update, list and files imports
    :param path: Path within the URL
    :return: Depends on the path, either a page a JSON
    """
    if not ac_fast_check_current_user_has_case_access(caseid, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=caseid)

    # Files uploads of a case. Get the files, create the folder tree
    # The request "add" will start the check + import of the files.
    f = request.files.get('file')

    is_update = request.form.get('is_update', type=str)
    pipeline = request.form.get('pipeline', '', type=str)

    try:
        pipeline_mod = pipeline.split("-")[0]
    except Exception as e:
        log.error(e.__str__())
        return response_error('Malformed request')

    if not iris_module_exists(pipeline_mod):
        return response_error('Missing pipeline')

    mod, _ = instantiate_module_from_name(pipeline_mod)
    status = configure_module_on_init(mod)
    if status.is_failure():
        return response_error("Path for upload {} is not built ! Unreachable pipeline".format(
            os.path.join(f.filename)))

    case_customer = None
    case_name = None

    if is_update == "true":
        case = get_case(caseid)

        if case:
            case_name = case.name
            case_customer = case.client.name

    else:
        case_name = urllib.parse.quote(request.form.get('case_name', '', type=str), safe='')
        case_customer = request.form.get('case_customer', type=str)

    fpath = build_upload_path(case_customer=case_customer,
                              case_name=urllib.parse.unquote(case_name),
                              module=pipeline_mod,
                              create=is_update
                              )

    f.filename = secure_filename(f.filename)
    status = mod.pipeline_files_upload(fpath, f, case_customer, case_name, is_update)

    if status.is_success():
        return response_success(status.get_message())

    return response_error(status.get_message())
