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

from app.db import db
from app.blueprints.iris_user import iris_current_user
from app.models.cases import CasesEvent
from app.models.errors import ObjectNotFoundError
from app.util import add_obj_history_entry
from app.datamgmt.states import update_timeline_state
from app.datamgmt.case.case_events_db import save_event_category
from app.datamgmt.case.case_events_db import update_event_assets
from app.models.errors import BusinessProcessingError
from app.datamgmt.case.case_events_db import update_event_iocs
from app.datamgmt.case.case_events_db import get_case_event
from app.datamgmt.case.case_events_db import delete_event
from app.iris_engine.utils.tracker import track_activity
from app.iris_engine.utils.collab import collab_notify
from app.iris_engine.module_handler.module_handler import call_modules_hook


def events_create(case_identifier, event: CasesEvent, event_category_id, event_assets, event_iocs, sync_iocs_assets) -> CasesEvent:

    event.case_id = case_identifier
    event.event_added = datetime.utcnow()
    event.user_id = iris_current_user.id

    add_obj_history_entry(event, 'created')

    db.session.add(event)
    update_timeline_state(case_identifier)
    db.session.commit()

    save_event_category(event.event_id, event_category_id)

    setattr(event, 'event_category_id', event_category_id)

    success, log = update_event_assets(event.event_id, case_identifier, event_assets, event_iocs, sync_iocs_assets)
    if not success:
        raise BusinessProcessingError('Error while saving linked assets', data=log)

    success, log = update_event_iocs(event.event_id, case_identifier, event_iocs)
    if not success:
        raise BusinessProcessingError('Error while saving linked iocs', data=log)

    setattr(event, 'event_category_id', event_category_id)

    event = call_modules_hook('on_postload_event_create', event, caseid=case_identifier)

    track_activity(f'added event "{event.event_title}"', caseid=case_identifier)
    return event


def events_get(identifier) -> CasesEvent:
    event = get_case_event(identifier)
    if not event:
        raise ObjectNotFoundError()
    return event


def events_update(event: CasesEvent, event_category_id, event_assets, event_iocs, event_sync_iocs_assets) -> CasesEvent:
    add_obj_history_entry(event, 'updated')

    update_timeline_state(event.case_id)
    db.session.commit()

    save_event_category(event.event_id, event_category_id)

    setattr(event, 'event_category_id', event_category_id)

    success, log = update_event_assets(event.event_id, event.case_id, event_assets, event_iocs, event_sync_iocs_assets)
    if not success:
        raise BusinessProcessingError('Error while saving linked assets', data=log)

    success, log = update_event_iocs(event.event_id, event.case_id, event_iocs)
    if not success:
        raise BusinessProcessingError('Error while saving linked iocs', data=log)

    event = call_modules_hook('on_postload_event_update', event, caseid=event.case_id)

    track_activity(f"updated event \"{event.event_title}\"", caseid=event.case_id)
    return event


def events_delete(user, event: CasesEvent):
    delete_event(user.id, event)

    call_modules_hook('on_postload_event_delete', event.event_id, caseid=event.case_id)
    collab_notify(event.case_id, 'events', 'deletion', event.event_id)
    track_activity(f'deleted event "{event.event_title}" in timeline', event.case_id)
