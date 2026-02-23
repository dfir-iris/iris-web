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

import logging as log
import os
import traceback
import urllib.parse

from flask import Blueprint
from flask import request
from werkzeug import Response
from werkzeug.utils import secure_filename
from marshmallow import ValidationError

from app.db import db
from app.blueprints.rest.parsing import parse_comma_separated_identifiers
from app.blueprints.rest.endpoints import endpoint_deprecated
from app.blueprints.iris_user import iris_current_user
from app.datamgmt.alerts.alerts_db import get_alert_status_by_name
from app.datamgmt.case.case_db import get_case
from app.datamgmt.iris_engine.modules_db import get_pipelines_args_from_name
from app.datamgmt.iris_engine.modules_db import iris_module_exists
from app.datamgmt.manage.manage_cases_db import get_filtered_cases
from app.datamgmt.manage.manage_cases_db import close_case, map_alert_resolution_to_case_status
from app.datamgmt.manage.manage_cases_db import get_case_details_rt
from app.datamgmt.manage.manage_cases_db import list_cases_dict
from app.datamgmt.manage.manage_cases_db import reopen_case
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
from app.blueprints.access_controls import ac_requires_case_identifier
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.access_controls import ac_current_user_has_customer_access
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.business.cases import cases_delete
from app.business.cases import cases_update
from app.business.cases import cases_create
from app.business.cases import cases_get_by_identifier
from app.models.errors import BusinessProcessingError
from app.iris_engine.module_handler.module_handler import call_deprecated_on_preload_modules_hook

manage_cases_rest_blueprint = Blueprint('manage_case_rest', __name__)


@manage_cases_rest_blueprint.route('/manage/cases/<int:identifier>', methods=['GET'])
@endpoint_deprecated('GET', '/api/v2/cases/<int:identifier>')
@ac_api_requires()
def get_case_api(identifier):
    if not ac_fast_check_current_user_has_case_access(identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=identifier)

    res = get_case_details_rt(identifier)
    if res:
        return response_success(data=res)

    return response_error(f'Case ID {identifier} not found')


@manage_cases_rest_blueprint.route('/manage/cases/filter', methods=['GET'])
@ac_api_requires()
def manage_case_filter() -> Response:

    pagination_parameters = parse_pagination_parameters(request)

    case_ids_str = request.args.get('case_ids', None, type=str)

    if case_ids_str:
        try:
            case_ids_str = parse_comma_separated_identifiers(case_ids_str)

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
        iris_current_user.id,
        pagination_parameters,
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
        search_value=search_value
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


@manage_cases_rest_blueprint.route('/manage/cases/delete/<int:identifier>', methods=['POST'])
@endpoint_deprecated('DELETE', '/api/v2/cases/<int:identifier>')
@ac_api_requires(Permissions.standard_user)
def api_delete_case(identifier):
    if not ac_fast_check_current_user_has_case_access(identifier, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=identifier)

    try:
        cases_delete(identifier)
        return response_success('Case successfully deleted')
    except BusinessProcessingError as e:
        return response_error(e.get_message())


@manage_cases_rest_blueprint.route('/manage/cases/reopen/<int:identifier>', methods=['POST'])
@ac_api_requires(Permissions.standard_user)
def api_reopen_case(identifier):
    if not ac_fast_check_current_user_has_case_access(identifier, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=identifier)

    if not identifier:
        return response_error("No case ID provided")

    case = get_case(identifier)
    if not case:
        return response_error("Tried to reopen an non-existing case")

    res = reopen_case(identifier)
    if not res:
        return response_error("Tried to reopen an non-existing case")

    # Reopen the related alerts
    if case.alerts:
        merged_status = get_alert_status_by_name('Merged')
        for alert in case.alerts:
            if alert.alert_status_id != merged_status.status_id:
                alert.alert_status_id = merged_status.status_id
                track_activity(f"alert ID {alert.alert_id} status updated to merged due to case #{identifier} being reopen",
                               caseid=identifier, ctx_less=False)

                db.session.add(alert)

    case = call_modules_hook('on_postload_case_update', case, caseid=identifier)

    add_obj_history_entry(case, 'case reopen')
    track_activity(f"reopen case ID {identifier}", caseid=identifier)
    case_schema = CaseSchema()

    return response_success("Case reopen successfully", data=case_schema.dump(res))


@manage_cases_rest_blueprint.route('/manage/cases/close/<int:identifier>', methods=['POST'])
@ac_api_requires(Permissions.standard_user)
def api_case_close(identifier):
    if not ac_fast_check_current_user_has_case_access(identifier, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=identifier)

    if not identifier:
        return response_error('No case ID provided')

    case = get_case(identifier)
    if not case:
        return response_error('Tried to close an non-existing case')

    res = close_case(identifier)
    if not res:
        return response_error('Tried to close an non-existing case')

    # Close the related alerts
    if case.alerts:
        close_status = get_alert_status_by_name('Closed')
        case_status_id_mapped = map_alert_resolution_to_case_status(case.status_id)

        for alert in case.alerts:
            if alert.alert_status_id != close_status.status_id:
                alert.alert_status_id = close_status.status_id
                alert = call_modules_hook('on_postload_alert_update', alert, caseid=identifier)

            if alert.alert_resolution_status_id != case_status_id_mapped:
                alert.alert_resolution_status_id = case_status_id_mapped
                alert = call_modules_hook('on_postload_alert_resolution_update', alert, caseid=identifier)

                track_activity(f'closing alert ID {alert.alert_id} due to case #{identifier} being closed',
                               caseid=identifier, ctx_less=False)

                db.session.add(alert)

    case = call_modules_hook('on_postload_case_update', case, caseid=identifier)

    add_obj_history_entry(case, 'case closed')
    track_activity(f'closed case ID {identifier}', caseid=identifier, ctx_less=False)
    case_schema = CaseSchema()

    return response_success('Case closed successfully', data=case_schema.dump(res))


@manage_cases_rest_blueprint.route('/manage/cases/add', methods=['POST'])
@endpoint_deprecated('POST', '/api/v2/cases')
@ac_api_requires(Permissions.standard_user)
def api_add_case():
    case_schema = CaseSchema()

    try:
        request_data = call_deprecated_on_preload_modules_hook('case_create', request.get_json())
        case = case_schema.load(request_data)
        case_template_id = request_data.pop('case_template_id', None)
        result = cases_create(iris_current_user, case, case_template_id)
        return response_success('Case created', data=case_schema.dump(result))
    except ValidationError as e:
        raise response_error('Data error', e.messages)
    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@manage_cases_rest_blueprint.route('/manage/cases/list', methods=['GET'])
@ac_api_requires(Permissions.standard_user)
def api_list_case():
    data = list_cases_dict(iris_current_user.id)

    return response_success("", data=data)


@manage_cases_rest_blueprint.route('/manage/cases/update/<int:identifier>', methods=['POST'])
@endpoint_deprecated('PUT', '/api/v2/cases/<int:identifier>')
@ac_api_requires(Permissions.standard_user)
def update_case_info(identifier):
    if not ac_fast_check_current_user_has_case_access(identifier, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=identifier)

    case_schema = CaseSchema()
    try:
        case = cases_get_by_identifier(identifier)

        request_data = request.get_json()
        # If user tries to update the customer, check if the user has access to the new customer
        if request_data.get('case_customer') and request_data.get('case_customer') != case.client_id:
            if not ac_current_user_has_customer_access(request_data.get('case_customer')):
                raise BusinessProcessingError('Invalid customer ID. Permission denied.')

        if 'case_name' in request_data:
            short_case_name = request_data.get('case_name').replace(f'#{case.case_id} - ', '')
            request_data['case_name'] = f'#{case.case_id} - {short_case_name}'
        request_data['case_customer'] = case.client_id if not request_data.get('case_customer') else request_data.get(
            'case_customer')
        request_data['reviewer_id'] = None if request_data.get('reviewer_id') == '' else request_data.get('reviewer_id')

        updated_case = case_schema.load(request_data, instance=case, partial=True)

        protagonists = request_data.get('protagonists')
        tags = request_data.get('case_tags')
        case = cases_update(case, updated_case, protagonists, tags)
        return response_success('Updated', data=case_schema.dump(case))
    except ValidationError as e:
        return response_error('Data error', e.messages)

    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@manage_cases_rest_blueprint.route('/manage/cases/trigger-pipeline', methods=['POST'])
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
        # We got some errors and cannot continue
        return response_error(status.get_message(), data=status.get_data())

    except Exception as _:
        traceback.print_exc()
        return response_error('Fail to update case', data=traceback.print_exc())


@manage_cases_rest_blueprint.route('/manage/cases/upload_files', methods=['POST'])
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
        return response_error(f"Path for upload {os.path.join(f.filename)} is not built ! Unreachable pipeline")

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
