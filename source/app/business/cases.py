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

from app.schema.marshables import CaseSchema

from app import app
from app import db

from app.util import add_obj_history_entry

from app.models.authorization import CaseAccessLevel
from app.models.authorization import Permissions
from app.models import ReviewStatusList

from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.iris_engine.access_control.utils import ac_set_new_case_access

from app.datamgmt.case.case_db import save_case_tags
from app.datamgmt.case.case_db import register_case_protagonists
from app.datamgmt.case.case_db import get_review_id_from_name
from app.datamgmt.alerts.alerts_db import get_alert_status_by_name
from app.datamgmt.manage.manage_case_templates_db import case_template_pre_modifier
from app.datamgmt.manage.manage_case_templates_db import case_template_post_modifier
from app.datamgmt.manage.manage_access_control_db import user_has_client_access
from app.datamgmt.manage.manage_case_state_db import get_case_state_by_name
from app.datamgmt.manage.manage_cases_db import delete_case
from app.datamgmt.manage.manage_cases_db import reopen_case
from app.datamgmt.manage.manage_cases_db import map_alert_resolution_to_case_status
from app.datamgmt.manage.manage_cases_db import close_case
from app.datamgmt.case.case_db import get_case

from app.business.errors import BusinessProcessingError
from app.business.permissions import check_current_user_has_some_case_access
from app.business.permissions import check_current_user_has_some_permission


def get_case_by_identifier(case_identifier):
    check_current_user_has_some_case_access(case_identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access])

    return get_case(case_identifier)


def _load(request_data, **kwargs):
    try:
        add_case_schema = CaseSchema()
        return add_case_schema.load(request_data, **kwargs)
    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)


def create(request_json):
    try:
        # TODO remove caseid doesn't seems to be useful for call_modules_hook => remove argument
        request_data = call_modules_hook('on_preload_case_create', request_json, None)
        case_template_id = request_data.pop('case_template_id', None)

        case = _load(request_data)
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

        # TODO remove caseid doesn't seems to be useful for call_modules_hook => remove argument
        case = call_modules_hook('on_postload_case_create', case, None)

        add_obj_history_entry(case, 'created')
        track_activity(f'new case "{case.name}" created', caseid=case.case_id, ctx_less=False)

        return case, 'Case created'

    # TODO maybe remove validationerror (because unnecessary)
    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)

    except Exception as e:
        log.error(e.__str__())
        log.error(traceback.format_exc())
        raise BusinessProcessingError('Error creating case - check server logs')


def delete(case_identifier):
    check_current_user_has_some_permission([Permissions.standard_user])
    check_current_user_has_some_case_access(case_identifier, [CaseAccessLevel.full_access])

    if case_identifier == 1:
        track_activity(f'tried to delete case {case_identifier}, but case is the primary case',
                       caseid=case_identifier, ctx_less=True)

        raise BusinessProcessingError('Cannot delete a primary case to keep consistency')

    try:
        call_modules_hook('on_preload_case_delete', data=case_identifier, caseid=case_identifier)
        if not delete_case(case_identifier):
            track_activity(f'tried to delete case {case_identifier}, but it doesn\'t exist',
                           caseid=case_identifier, ctx_less=True)
            raise BusinessProcessingError('Tried to delete a non-existing case')
        call_modules_hook('on_postload_case_delete', data=case_identifier, caseid=case_identifier)
        track_activity(f'case {case_identifier} deleted successfully', ctx_less=True)
    except Exception as e:
        app.logger.exception(e)
        raise BusinessProcessingError('Cannot delete the case. Please check server logs for additional informations')


def update(case_identifier, request_data):
    check_current_user_has_some_permission([Permissions.standard_user])
    check_current_user_has_some_case_access(case_identifier, [CaseAccessLevel.full_access])

    case_i = get_case(case_identifier)
    if not case_i:
        raise BusinessProcessingError('Case not found')

    try:

        previous_case_state = case_i.state_id
        case_previous_reviewer_id = case_i.reviewer_id
        closed_state_id = get_case_state_by_name('Closed').state_id

        # If user tries to update the customer, check if the user has access to the new customer
        if request_data.get('case_customer') and request_data.get('case_customer') != case_i.client_id:
            if not user_has_client_access(current_user.id, request_data.get('case_customer')):
                raise BusinessProcessingError('Invalid customer ID. Permission denied.')

        if 'case_name' in request_data:
            short_case_name = request_data.get('case_name').replace(f'#{case_i.case_id} - ', '')
            request_data['case_name'] = f'#{case_i.case_id} - {short_case_name}'
        request_data['case_customer'] = case_i.client_id if not request_data.get('case_customer') else request_data.get(
            'case_customer')
        request_data['reviewer_id'] = None if request_data.get('reviewer_id') == '' else request_data.get('reviewer_id')

        case = _load(request_data, instance=case_i, partial=True)

        db.session.commit()

        if previous_case_state != case.state_id:
            if case.state_id == closed_state_id:
                track_activity('case closed', caseid=case_identifier)
                res = close_case(case_identifier)
                if not res:
                    raise BusinessProcessingError('Tried to close an non-existing case')

                # Close the related alerts
                if case.alerts:
                    close_status = get_alert_status_by_name('Closed')
                    case_status_id_mapped = map_alert_resolution_to_case_status(case.status_id)

                    for alert in case.alerts:
                        if alert.alert_status_id != close_status.status_id:
                            alert.alert_status_id = close_status.status_id
                            alert = call_modules_hook('on_postload_alert_update', data=alert, caseid=case_identifier)

                        if alert.alert_resolution_status_id != case_status_id_mapped:
                            alert.alert_resolution_status_id = case_status_id_mapped
                            alert = call_modules_hook('on_postload_alert_resolution_update', data=alert,
                                                      caseid=case_identifier)

                            track_activity(
                                f'closing alert ID {alert.alert_id} due to case #{case_identifier} being closed',
                                caseid=case_identifier, ctx_less=False)

                            db.session.add(alert)

            elif previous_case_state == closed_state_id and case.state_id != closed_state_id:
                track_activity('case re-opened', caseid=case_identifier)
                res = reopen_case(case_identifier)
                if not res:
                    raise BusinessProcessingError('Tried to re-open an non-existing case')

        if case_previous_reviewer_id != case.reviewer_id:
            if case.reviewer_id is None:
                track_activity('case reviewer removed', caseid=case_identifier)
                case.review_status_id = get_review_id_from_name(ReviewStatusList.not_reviewed)
            else:
                track_activity('case reviewer changed', caseid=case_identifier)

        register_case_protagonists(case.case_id, request_data.get('protagonists'))
        save_case_tags(request_data.get('case_tags'), case_i)

        case = call_modules_hook('on_postload_case_update', data=case, caseid=case_identifier)

        add_obj_history_entry(case_i, 'case info updated')
        track_activity(f'case updated "{case.name}"', caseid=case_identifier)

        return case, 'updated'

    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)

    except Exception as e:
        log.error(e.__str__())
        log.error(traceback.format_exc())
        raise BusinessProcessingError('Error updating case - check server logs')
