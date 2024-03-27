#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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
import traceback

from flask_login import current_user
from marshmallow.exceptions import ValidationError

from app import app
from app.util import add_obj_history_entry
from app.models.authorization import CaseAccessLevel
from app.models.authorization import Permissions
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.iris_engine.access_control.utils import ac_set_new_case_access
from app.datamgmt.manage.manage_case_templates_db import case_template_pre_modifier
from app.datamgmt.manage.manage_case_templates_db import case_template_post_modifier
from app.datamgmt.manage.manage_case_state_db import get_case_state_by_name
from app.datamgmt.manage.manage_cases_db import delete_case
from app.business.errors import BusinessProcessingError
from app.business.permissions import check_current_user_has_some_case_access
from app.business.permissions import check_current_user_has_some_permission
from app.schema.marshables import CaseSchema


def _load(request_data):
    try:
        add_case_schema = CaseSchema()
        return add_case_schema.load(request_data)
    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)

#case_schema must be changed
def create(request_json, case_identifier):

    try:
        request_data = call_modules_hook('on_preload_case_create', data=request_json, caseid=case_identifier)
        case = _load(request_data)

        case_template_id = request_data.pop("case_template_id", None)
        case.owner_id = current_user.id
        case.severity_id = 4

        if case_template_id and len(case_template_id) > 0:
            case = case_template_pre_modifier(case, case_template_id)
            if case is None:
                raise BusinessProcessingError(f'Invalid Case template ID {case_template_id}')

        case.state_id = get_case_state_by_name('Open').state_id

        case.save()

        if case_template_id and len(case_template_id) > 0:
            try:
                case, logs = case_template_post_modifier(case, case_template_id)
                if len(logs) > 0:
                    raise BusinessProcessingError(f'Could not update new case with {case_template_id}', logs)

            except Exception as e:
                log.error(e.__str__())
                raise BusinessProcessingError(f'Unexpected error when loading template {case_template_id} to new case.')

        ac_set_new_case_access(None, case.case_id, case.client_id)

        case = call_modules_hook('on_postload_case_create', data=case, caseid=case_identifier)

        add_obj_history_entry(case, 'created')
        track_activity("new case {case_name} created".format(case_name=case.name), caseid=case.case_id, ctx_less=False)

        return case, 'Case created'

    #TODO maybe remove validationerror (because unnecessary)
    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)

    except Exception as e:
        log.error(e.__str__())
        log.error(traceback.format_exc())
        raise BusinessProcessingError('Error creating case - check server logs')


def delete(case_identifier, context_case_identifier):
    check_current_user_has_some_permission([Permissions.standard_user])
    check_current_user_has_some_case_access(case_identifier, [CaseAccessLevel.full_access])

    if case_identifier == 1:
        track_activity(f'tried to delete case {case_identifier}, but case is the primary case',
                       caseid=context_case_identifier, ctx_less=True)

        raise BusinessProcessingError('Cannot delete a primary case to keep consistency')

    try:
        call_modules_hook('on_preload_case_delete', data=case_identifier, caseid=context_case_identifier)
        if not delete_case(case_identifier):
            track_activity(f'tried to delete case {case_identifier}, but it doesn\'t exist',
                           caseid=context_case_identifier, ctx_less=True)
            raise BusinessProcessingError('Tried to delete a non-existing case')
        call_modules_hook('on_postload_case_delete', data=case_identifier, caseid=context_case_identifier)
        track_activity(f'case {case_identifier} deleted successfully', ctx_less=True)
    except Exception as e:
        app.logger.exception(e)
        raise BusinessProcessingError('Cannot delete the case. Please check server logs for additional informations')

