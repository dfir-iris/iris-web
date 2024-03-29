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

from flask_login import current_user
from marshmallow.exceptions import ValidationError

from app.models.authorization import CaseAccessLevel
from app.datamgmt.case.case_iocs_db import add_ioc
from app.datamgmt.case.case_iocs_db import add_ioc_link
from app.datamgmt.case.case_iocs_db import check_ioc_type_id
from app.datamgmt.case.case_iocs_db import get_ioc
from app.datamgmt.case.case_iocs_db import delete_ioc
from app.schema.marshables import IocSchema
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.business.errors import BusinessProcessingError
from app.business.permissions import check_current_user_has_some_case_access_stricter


def _load(request_data):
    try:
        add_ioc_schema = IocSchema()
        return add_ioc_schema.load(request_data)
    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)


def create(request_json, case_identifier):
    check_current_user_has_some_case_access_stricter([CaseAccessLevel.full_access])

    # TODO ideally schema validation should be done before, outside the business logic in the REST API
    #      for that the hook should be called after schema validation
    request_data = call_modules_hook('on_preload_ioc_create', data=request_json, caseid=case_identifier)
    ioc = _load(request_data)

    if not check_ioc_type_id(type_id=ioc.ioc_type_id):
        raise BusinessProcessingError('Not a valid IOC type')

    ioc, existed = add_ioc(ioc=ioc, user_id=current_user.id, caseid=case_identifier)

    link_existed = add_ioc_link(ioc.ioc_id, case_identifier)

    if link_existed:
        # note: I am no big fan of returning tuples.
        # It is a code smell some type is missing, or the code is badly designed.
        return ioc, 'IOC already exists and linked to this case'

    if not link_existed:
        ioc = call_modules_hook('on_postload_ioc_create', data=ioc, caseid=case_identifier)

    if ioc:
        track_activity(f'added ioc "{ioc.ioc_value}"', caseid=case_identifier)

        msg = "IOC already existed in DB. Updated with info on DB." if existed else "IOC added"
        return ioc, msg

    raise BusinessProcessingError('Unable to create IOC for internal reasons')


def remove_from_case(identifier, case_identifier):
    call_modules_hook('on_preload_ioc_delete', data=identifier, caseid=case_identifier)
    ioc = get_ioc(identifier, case_identifier)

    if not ioc:
        raise BusinessProcessingError('Not a valid IOC for this case')

    if not delete_ioc(ioc, case_identifier):
        track_activity(f"unlinked IOC ID {ioc.ioc_value}", caseid=case_identifier)
        return f'IOC {identifier} unlinked'

    call_modules_hook('on_postload_ioc_delete', data=identifier, caseid=case_identifier)

    track_activity(f"deleted IOC \"{ioc.ioc_value}\"", caseid=case_identifier)
    return f'IOC {identifier} deleted'
