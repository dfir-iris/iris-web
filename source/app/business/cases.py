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

import datetime
import traceback

from app.db import db
from app.logger import logger
from app.util import add_obj_history_entry
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.business.iocs import iocs_exports_to_json
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.iris_engine.access_control.utils import ac_set_new_case_access
from app.datamgmt.case.case_db import case_db_exists
from app.datamgmt.case.case_db import list_user_cases
from app.datamgmt.case.case_db import case_db_save
from app.datamgmt.case.case_db import list_user_reviews
from app.datamgmt.case.case_db import save_case_tags
from app.datamgmt.case.case_db import register_case_protagonists
from app.datamgmt.case.case_db import get_review_id_from_name
from app.datamgmt.alerts.alerts_db import get_alert_status_by_name
from app.datamgmt.manage.manage_case_templates_db import case_template_pre_modifier
from app.datamgmt.manage.manage_case_templates_db import case_template_post_modifier
from app.datamgmt.manage.manage_case_state_db import get_case_state_by_name
from app.datamgmt.manage.manage_cases_db import delete_case
from app.datamgmt.manage.manage_cases_db import reopen_case
from app.datamgmt.manage.manage_cases_db import map_alert_resolution_to_case_status
from app.datamgmt.manage.manage_cases_db import close_case
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_db import get_first_case
from app.datamgmt.reporter.report_db import export_caseinfo_json
from app.datamgmt.reporter.report_db import process_md_images_links_for_report
from app.datamgmt.reporter.report_db import export_case_evidences_json
from app.datamgmt.reporter.report_db import export_case_tm_json
from app.datamgmt.reporter.report_db import export_case_assets_json
from app.datamgmt.reporter.report_db import export_case_tasks_json
from app.datamgmt.reporter.report_db import export_case_comments_json
from app.datamgmt.reporter.report_db import export_case_notes_json
from app.datamgmt.manage.manage_cases_db import get_filtered_cases
from app.datamgmt.case.case_db import get_first_case_with_customer
from app.models.cases import Cases
from app.models.cases import ReviewStatusList
from app.models.customers import Client


def cases_filter(current_user, pagination_parameters, name, case_identifiers, customer_identifier,
                 description, classification_identifier, owner_identifier, opening_user_identifier,
                 severity_identifier, status_identifier, soc_identifier,
                 start_open_date, end_open_date, is_open):
    return get_filtered_cases(current_user.id, pagination_parameters,
            start_open_date,
            end_open_date,
            customer_identifier,
            case_identifiers,
            name,
            description,
            classification_identifier,
            owner_identifier,
            opening_user_identifier,
            severity_identifier,
            status_identifier,
            soc_identifier,
            search_value='',
            is_open=is_open)


def cases_filter_by_user(user, show_all: bool):
    return list_user_cases(user.id, show_all)


def cases_filter_by_reviewer(user):
    return list_user_reviews(user.id)


def cases_get_by_identifier(case_identifier) -> Cases:
    case = get_case(case_identifier)
    if case is None:
        raise ObjectNotFoundError()
    return case


def cases_get_first() -> Cases:
    return get_first_case()


def cases_get_first_with_customer(client: Client) -> Cases:
    return get_first_case_with_customer(client.client_id)


def cases_exists(identifier):
    return case_db_exists(identifier)


def cases_create(user, case: Cases, case_template_id) -> Cases:
    case.owner_id = user.id
    case.severity_id = 4

    if case_template_id and len(case_template_id) > 0:
        case = case_template_pre_modifier(case, case_template_id)
        if case is None:
            raise BusinessProcessingError(f'Invalid Case template ID {case_template_id}')

    case.state_id = get_case_state_by_name('Open').state_id

    case_db_save(case)

    if case_template_id and len(case_template_id) > 0:
        try:
            case, logs = case_template_post_modifier(case, case_template_id)
            if len(logs) > 0:
                raise BusinessProcessingError(f'Could not update new case with {case_template_id}', logs)

        except Exception as e:
            logger.error(e.__str__())
            raise BusinessProcessingError(f'Unexpected error when loading template {case_template_id} to new case.')

    ac_set_new_case_access(user, case.case_id, case.client_id)

    case = call_modules_hook('on_postload_case_create', case)

    add_obj_history_entry(case, 'created')
    track_activity(f'new case "{case.name}" created', caseid=case.case_id, ctx_less=False)

    return case


def cases_delete(case_identifier):
    if case_identifier == 1:
        track_activity(f'tried to delete case {case_identifier}, but case is the primary case',
                       caseid=case_identifier, ctx_less=True)

        raise BusinessProcessingError('Cannot delete a primary case to keep consistency')

    try:
        call_modules_hook('on_preload_case_delete', case_identifier, caseid=case_identifier)
        if not delete_case(case_identifier):
            track_activity(f'tried to delete case {case_identifier}, but it doesn\'t exist',
                           caseid=case_identifier, ctx_less=True)
            raise BusinessProcessingError('Tried to delete a non-existing case')
        call_modules_hook('on_postload_case_delete', case_identifier, caseid=case_identifier)
        track_activity(f'case {case_identifier} deleted successfully', ctx_less=True)
    except Exception as e:
        logger.exception(e)
        raise BusinessProcessingError('Cannot delete the case. Please check server logs for additional informations')


def cases_update(case: Cases, updated_case, protagonists, tags, previous_state_id=None) -> Cases:
    try:
        closed_state_id = get_case_state_by_name('Closed').state_id
        previous_case_state = case.state_id if previous_state_id is None else previous_state_id
        case_previous_reviewer_id = case.reviewer_id
        db.session.commit()

        if previous_case_state != updated_case.state_id:
            if updated_case.state_id == closed_state_id:
                track_activity('case closed', caseid=case.case_id)
                res = close_case(case.case_id)
                if not res:
                    raise BusinessProcessingError('Tried to close an non-existing case')

                # Close the related alerts
                if updated_case.alerts:
                    close_status = get_alert_status_by_name('Closed')
                    case_status_id_mapped = map_alert_resolution_to_case_status(updated_case.status_id)

                    for alert in updated_case.alerts:
                        if alert.alert_status_id != close_status.status_id:
                            alert.alert_status_id = close_status.status_id
                            alert = call_modules_hook('on_postload_alert_update', alert, caseid=case.case_id)

                        if alert.alert_resolution_status_id != case_status_id_mapped:
                            alert.alert_resolution_status_id = case_status_id_mapped
                            alert = call_modules_hook('on_postload_alert_resolution_update', alert,
                                                      caseid=case.case_id)

                            track_activity(
                                f'closing alert ID {alert.alert_id} due to case #{case.case_id} being closed',
                                caseid=case.case_id, ctx_less=False)

                            db.session.add(alert)

            elif previous_case_state == closed_state_id and updated_case.state_id != closed_state_id:
                track_activity('case re-opened', caseid=case.case_id)
                res = reopen_case(case.case_id, updated_case.state_id)
                if not res:
                    raise BusinessProcessingError('Tried to re-open an non-existing case')

        if case_previous_reviewer_id != updated_case.reviewer_id:
            if updated_case.reviewer_id is None:
                track_activity('case reviewer removed', caseid=case.case_id)
                updated_case.review_status_id = get_review_id_from_name(ReviewStatusList.not_reviewed)
            else:
                track_activity('case reviewer changed', caseid=case.case_id)

        register_case_protagonists(updated_case.case_id, protagonists)
        save_case_tags(tags, case)

        updated_case = call_modules_hook('on_postload_case_update', data=updated_case, caseid=case.case_id)

        add_obj_history_entry(case, 'case info updated')
        track_activity(f'case updated "{updated_case.name}"', caseid=case.case_id)

        return updated_case

    except BusinessProcessingError as e:
        raise e

    except Exception as e:
        logger.error(e.__str__())
        logger.error(traceback.format_exc())
        raise BusinessProcessingError('Data error', str(e))


def cases_export_to_json(case_id):
    """Fully export a case a JSON"""
    export = {}
    case = export_caseinfo_json(case_id)

    if not case:
        export['errors'] = ['Invalid case number']
        return export

    case['description'] = process_md_images_links_for_report(case['description'])

    export['case'] = case
    export['evidences'] = export_case_evidences_json(case_id)
    export['timeline'] = export_case_tm_json(case_id)
    export['iocs'] = iocs_exports_to_json(case_id)
    export['assets'] = export_case_assets_json(case_id)
    export['tasks'] = export_case_tasks_json(case_id)
    export['comments'] = export_case_comments_json(case_id)
    export['notes'] = export_case_notes_json(case_id)
    export['export_date'] = datetime.datetime.utcnow()

    return export
