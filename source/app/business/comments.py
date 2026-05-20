#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
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

from flask_sqlalchemy.pagination import Pagination

from app.db import db
from app.business.alerts import alerts_exists
from app.business.alerts import alerts_get
from app.models.errors import ObjectNotFoundError
from app.models.errors import BusinessProcessingError
from app.datamgmt.case.case_comments import get_case_comment
from app.datamgmt.comments import get_filtered_alert_comments
from app.datamgmt.comments import get_filtered_asset_comments
from app.datamgmt.comments import get_filtered_evidence_comments
from app.datamgmt.comments import get_filtered_ioc_comments
from app.datamgmt.comments import get_filtered_note_comments
from app.datamgmt.comments import get_filtered_task_comments
from app.datamgmt.comments import get_filtered_event_comments
from app.datamgmt.comments import delete_comment
from app.datamgmt.case.case_assets_db import add_comment_to_asset
from app.datamgmt.case.case_rfiles_db import add_comment_to_evidence
from app.datamgmt.case.case_iocs_db import add_comment_to_ioc
from app.datamgmt.case.case_notes_db import add_comment_to_note
from app.datamgmt.case.case_tasks_db import add_comment_to_task
from app.datamgmt.case.case_events_db import add_comment_to_event
from app.datamgmt.case.case_assets_db import get_case_asset_comment
from app.datamgmt.case.case_rfiles_db import get_case_evidence_comment
from app.datamgmt.case.case_iocs_db import get_case_ioc_comment
from app.datamgmt.case.case_notes_db import get_case_note_comment
from app.datamgmt.case.case_tasks_db import get_case_task_comment
from app.datamgmt.case.case_events_db import get_case_event_comment
from app.datamgmt.case.case_assets_db import delete_asset_comment
from app.datamgmt.case.case_rfiles_db import delete_evidence_comment
from app.datamgmt.case.case_iocs_db import delete_ioc_comment
from app.datamgmt.case.case_notes_db import delete_note_comment
from app.datamgmt.case.case_tasks_db import delete_task_comment
from app.datamgmt.case.case_events_db import delete_event_comment
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.comments import Comments
from app.models.assets import CaseAssets
from app.models.evidences import CaseReceivedFile
from app.models.iocs import Ioc
from app.models.models import Notes
from app.models.models import CaseTasks
from app.models.cases import CasesEvent
from app.models.pagination_parameters import PaginationParameters
from app.util import add_obj_history_entry
from app.datamgmt.alerts.alerts_db import get_alert_comment
from app.models.alerts import Alert


def comments_get_filtered_by_alert(current_user, permissions, alert_identifier: int, pagination_parameters: PaginationParameters, fallback_customer_access=None) -> Pagination:
    if not alerts_exists(current_user, permissions, alert_identifier, fallback_customer_access):
        raise ObjectNotFoundError()

    return get_filtered_alert_comments(alert_identifier, pagination_parameters)


def comments_get_filtered_by_asset(asset: CaseAssets, pagination_parameters: PaginationParameters) -> Pagination:
    return get_filtered_asset_comments(asset.asset_id, pagination_parameters)


def comments_get_filtered_by_evidence(evidence: CaseReceivedFile, pagination_parameters: PaginationParameters) -> Pagination:
    return get_filtered_evidence_comments(evidence.id, pagination_parameters)


def comments_get_filtered_by_ioc(ioc: Ioc, pagination_parameters: PaginationParameters) -> Pagination:
    return get_filtered_ioc_comments(ioc.ioc_id, pagination_parameters)


def comments_get_filtered_by_note(note: Notes, pagination_parameters: PaginationParameters) -> Pagination:
    return get_filtered_note_comments(note.note_id, pagination_parameters)


def comments_get_filtered_by_task(task: CaseTasks, pagination_parameters: PaginationParameters) -> Pagination:
    return get_filtered_task_comments(task.id, pagination_parameters)


def comments_get_filtered_by_event(event: CasesEvent, pagination_parameters: PaginationParameters) -> Pagination:
    return get_filtered_event_comments(event.event_id, pagination_parameters)


def comments_update_for_case(current_user, comment_text, comment_id, object_type, caseid) -> Comments:
    comment = get_case_comment(comment_id, caseid)
    if not comment:
        raise BusinessProcessingError('Invalid comment ID')

    if comment.comment_user_id != current_user.id:
        raise BusinessProcessingError('Permission denied')

    comment.comment_text = comment_text
    comment.comment_update_date = datetime.utcnow()

    db.session.commit()

    hook = object_type
    if hook.endswith('s'):
        hook = hook[:-1]

    call_modules_hook(f'on_postload_{hook}_comment_update', comment, caseid=caseid)

    track_activity(f'comment {comment.comment_id} on {object_type} edited', caseid=caseid)
    return comment


def comments_create_for_alert(current_user, permissions, comment: Comments, alert_identifier: int, fallback_customer_access=None):
    alert = alerts_get(current_user, permissions, alert_identifier, fallback_customer_access)
    comment.comment_alert_id = alert_identifier
    comment.comment_user_id = current_user.id
    comment.comment_date = datetime.now()
    comment.comment_update_date = datetime.now()

    db.session.add(comment)

    add_obj_history_entry(alert, 'commented')
    db.session.commit()

    hook_data = {
        'comment': comment,
        'alert': alert
    }
    call_modules_hook('on_postload_alert_commented', hook_data)
    track_activity(f'alert "{alert.alert_id}" commented', ctx_less=True)


def comments_create_for_asset(current_user, asset: CaseAssets, comment: Comments):
    _create_comment(current_user, comment, asset.case_id)

    add_comment_to_asset(asset.asset_id, comment.comment_id)

    db.session.commit()

    hook_data = {
        'comment': comment,
        'asset': asset
    }
    call_modules_hook('on_postload_asset_commented', hook_data, caseid=asset.case_id)

    track_activity(f'asset "{asset.asset_name}" commented', caseid=asset.case_id)


def comments_create_for_evidence(current_user, evidence: CaseReceivedFile, comment: Comments):
    _create_comment(current_user, comment, evidence.case_id)

    add_comment_to_evidence(evidence.id, comment.comment_id)

    db.session.commit()

    hook_data = {
        'comment': comment,
        'evidence': evidence
    }
    call_modules_hook('on_postload_evidence_commented', hook_data, caseid=evidence.case_id)
    track_activity(f'evidence "{evidence.filename}" commented', caseid=evidence.case_id)


def comments_create_for_ioc(current_user, ioc: Ioc, comment: Comments):
    _create_comment(current_user, comment, ioc.case_id)

    add_comment_to_ioc(ioc.ioc_id, comment.comment_id)

    db.session.commit()

    hook_data = {
        'comment': comment,
        'ioc': ioc
    }
    call_modules_hook('on_postload_ioc_commented', hook_data, caseid=ioc.case_id)
    track_activity(f'ioc "{ioc.ioc_value}" commented', caseid=ioc.case_id)


def comments_create_for_note(current_user, note: Notes, comment: Comments):
    _create_comment(current_user, comment, note.note_case_id)

    add_comment_to_note(note.note_id, comment.comment_id)

    db.session.commit()

    hook_data = {
        'comment': comment,
        'note': note
    }
    call_modules_hook('on_postload_note_commented', hook_data, caseid=note.note_case_id)

    track_activity(f'note "{note.note_title}" commented', caseid=note.note_case_id)


def comments_create_for_task(current_user, task: CaseTasks, comment: Comments):
    _create_comment(current_user, comment, task.task_case_id)

    add_comment_to_task(task.id, comment.comment_id)

    db.session.commit()

    hook_data = {
        'comment': comment,
        'task': task
    }
    call_modules_hook('on_postload_task_commented', hook_data, caseid=task.task_case_id)

    track_activity(f'task "{task.task_title}" commented', caseid=task.task_case_id)


def comments_create_for_event(current_user, event: CasesEvent, comment: Comments):
    _create_comment(current_user, comment, event.case_id)

    add_comment_to_event(event.event_id, comment.comment_id)

    add_obj_history_entry(event, 'commented')

    db.session.commit()

    hook_data = {
        'comment': comment,
        'event': event
    }
    call_modules_hook('on_postload_event_commented', hook_data, caseid=event.case_id)

    track_activity(f'event "{event.event_title}" commented', caseid=event.case_id)


def _create_comment(current_user, comment, case_identifier):
    comment.comment_case_id = case_identifier
    comment.comment_user_id = current_user.id
    comment.comment_date = datetime.now()
    comment.comment_update_date = datetime.now()
    db.session.add(comment)
    db.session.commit()


def comments_get_for_alert(alert: Alert, identifier) -> Comments:
    comment = get_alert_comment(alert.alert_id, identifier)
    if comment is None:
        raise ObjectNotFoundError
    return comment


def comments_get_for_asset(asset: CaseAssets, identifier) -> Comments:
    comment = get_case_asset_comment(asset.asset_id, identifier)
    if comment is None:
        raise ObjectNotFoundError
    return comment


def comments_get_for_evidence(evidence: CaseReceivedFile, identifier) -> Comments:
    comment = get_case_evidence_comment(evidence.id, identifier)
    if comment is None:
        raise ObjectNotFoundError
    return comment


def comments_get_for_ioc(ioc: Ioc, identifier) -> Comments:
    comment = get_case_ioc_comment(ioc.ioc_id, identifier)
    if comment is None:
        raise ObjectNotFoundError
    return comment


def comments_get_for_note(note: Notes, identifier) -> Comments:
    comment = get_case_note_comment(note.note_id, identifier)
    if comment is None:
        raise ObjectNotFoundError
    return comment


def comments_get_for_task(task: CaseTasks, identifier) -> Comments:
    comment = get_case_task_comment(task.id, identifier)
    if comment is None:
        raise ObjectNotFoundError
    return comment


def comments_get_for_event(event: CasesEvent, identifier) -> Comments:
    comment = get_case_event_comment(event.event_id, identifier)
    if comment is None:
        raise ObjectNotFoundError
    return comment


def comments_delete_for_alert(comment: Comments):
    delete_comment(comment)

    call_modules_hook('on_postload_alert_comment_delete', comment.comment_id)
    track_activity(f'comment {comment.comment_id} on alert {comment.comment_alert_id} deleted', ctx_less=True)


def comments_delete_for_asset(asset: CaseAssets, comment: Comments):
    delete_asset_comment(asset.asset_id, comment)

    call_modules_hook('on_postload_asset_comment_delete', comment.comment_id, caseid=comment.comment_case_id)
    track_activity(f'comment {comment.comment_id} on asset {asset.asset_id} deleted', caseid=comment.comment_case_id)


def comments_delete_for_evidence(user, evidence: CaseReceivedFile, comment: Comments):
    delete_evidence_comment(user.id, evidence.id, comment.comment_id)

    call_modules_hook('on_postload_evidence_comment_delete', comment.comment_id, caseid=comment.comment_case_id)
    track_activity(f'comment {comment.comment_id} on evidence {evidence.id} deleted', caseid=comment.comment_case_id)


def comments_delete_for_ioc(user, ioc: Ioc, comment: Comments):
    delete_ioc_comment(user.id, ioc.ioc_id, comment.comment_id)

    call_modules_hook('on_postload_ioc_comment_delete', comment.comment_id, caseid=comment.comment_case_id)
    track_activity(f'comment {comment.comment_id} on ioc {ioc.ioc_id} deleted', caseid=comment.comment_case_id)


def comments_delete_for_note(user, note: Notes, comment: Comments):
    delete_note_comment(user.id, note.note_id, comment.comment_id)

    call_modules_hook('on_postload_note_comment_delete', comment.comment_id, caseid=comment.comment_case_id)
    track_activity(f'comment {comment.comment_id} on note {note.note_id} deleted', caseid=comment.comment_case_id)


def comments_delete_for_task(user, task: CaseTasks, comment: Comments):
    delete_task_comment(user.id, task.id, comment.comment_id)

    call_modules_hook('on_postload_task_comment_delete', comment.comment_id, caseid=comment.comment_case_id)
    track_activity(f'comment {comment.comment_id} on task {task.id} deleted', caseid=comment.comment_case_id)


def comments_delete_for_event(user, event: CasesEvent, comment: Comments):
    delete_event_comment(user.id, event.event_id, comment.comment_id)

    call_modules_hook('on_postload_event_comment_delete', comment.comment_id, caseid=comment.comment_case_id)
    track_activity(f'comment {comment.comment_id} on event {event.event_id} deleted', caseid=comment.comment_case_id)
