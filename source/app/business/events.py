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

import marshmallow
from flask_login import current_user
from marshmallow.exceptions import ValidationError

from app.wsgi import db
from app.models.cases import CasesEvent
from app.business.errors import ObjectNotFoundError
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.schema.marshables import EventSchema
from app.util import add_obj_history_entry
from app.datamgmt.states import update_timeline_state
from app.datamgmt.case.case_events_db import save_event_category
from app.datamgmt.case.case_events_db import update_event_assets
from app.business.errors import BusinessProcessingError
from app.datamgmt.case.case_events_db import update_event_iocs
from app.iris_engine.utils.tracker import track_activity
from app.datamgmt.case.case_events_db import get_case_event


def _load(request_data, **kwargs):
    try:
        schema = EventSchema()
        event = schema.load(request_data, **kwargs)
        event.event_date, event.event_date_wtz = schema.validate_date(request_data.get(u'event_date'),
                                                                      request_data.get(u'event_tz'))
        return event
    except ValidationError as e:
        raise BusinessProcessingError('Data error', data=e.normalized_messages())


def events_create(case_identifier, request_json) -> CasesEvent:
    request_data = call_modules_hook('on_preload_event_create', data=request_json, caseid=case_identifier)

    event = _load(request_data)

    event.case_id = case_identifier
    event.event_added = datetime.utcnow()
    event.user_id = current_user.id

    add_obj_history_entry(event, 'created')

    db.session.add(event)
    update_timeline_state(caseid=case_identifier)
    db.session.commit()

    save_event_category(event.event_id, request_data.get('event_category_id'))

    setattr(event, 'event_category_id', request_data.get('event_category_id'))
    sync_iocs_assets = request_data.get('event_sync_iocs_assets', False)

    success, log = update_event_assets(event.event_id, case_identifier, request_data.get('event_assets'),
                                       request_data.get('event_iocs'), sync_iocs_assets)
    if not success:
        raise BusinessProcessingError('Error while saving linked assets', data=log)

    success, log = update_event_iocs(event_id=event.event_id,
                                     caseid=case_identifier,
                                     iocs_list=request_data.get('event_iocs'))
    if not success:
        raise BusinessProcessingError('Error while saving linked iocs', data=log)

    setattr(event, 'event_category_id', request_data.get('event_category_id'))

    event = call_modules_hook('on_postload_event_create', data=event, caseid=case_identifier)

    track_activity(f'added event "{event.event_title}"', caseid=case_identifier)
    return event


def events_get(identifier) -> CasesEvent:
    event = get_case_event(identifier)
    if not event:
        raise ObjectNotFoundError()
    return event


def events_update(event: CasesEvent, request_json: dict) -> CasesEvent:
    try:
        request_data = call_modules_hook('on_preload_event_update', data=request_json, caseid=event.case_id)

        request_data['event_id'] = event.event_id
        event = _load(request_data, instance=event)

        add_obj_history_entry(event, 'updated')

        update_timeline_state(caseid=event.case_id)
        db.session.commit()

        save_event_category(event.event_id, request_data.get('event_category_id'))

        setattr(event, 'event_category_id', request_data.get('event_category_id'))

        success, log = update_event_assets(event.event_id, event.case_id, request_data.get('event_assets'),
                                           request_data.get('event_iocs'), request_data.get('event_sync_iocs_assets'))
        if not success:
            raise BusinessProcessingError('Error while saving linked assets', data=log)

        success, log = update_event_iocs(event_id=event.event_id,
                                         caseid=event.case_id,
                                         iocs_list=request_data.get('event_iocs'))
        if not success:
            raise BusinessProcessingError('Error while saving linked iocs', data=log)

        event = call_modules_hook('on_postload_event_update', data=event, caseid=event.case_id)

        track_activity(f"updated event \"{event.event_title}\"", caseid=event.case_id)
        return event
    except marshmallow.exceptions.ValidationError as e:
        raise BusinessProcessingError('Data error', data=e.normalized_messages())
