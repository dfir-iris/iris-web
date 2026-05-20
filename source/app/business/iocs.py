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


from app.db import db
from app.blueprints.iris_user import iris_current_user
from app.models.iocs import Ioc
from app.datamgmt.case.case_iocs_db import add_ioc
from app.datamgmt.case.case_iocs_db import case_iocs_db_exists
from app.datamgmt.case.case_iocs_db import check_ioc_type_id
from app.datamgmt.case.case_iocs_db import get_iocs
from app.datamgmt.case.case_iocs_db import delete_ioc
from app.datamgmt.states import update_ioc_state
from app.schema.marshables import IocSchema
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.datamgmt.case.case_iocs_db import get_ioc
from app.util import add_obj_history_entry
from app.datamgmt.case.case_iocs_db import get_filtered_iocs


def iocs_get(ioc_identifier) -> Ioc:
    ioc = get_ioc(ioc_identifier)
    if not ioc:
        raise ObjectNotFoundError()
    return ioc


def iocs_create(ioc: Ioc):

    if not ioc:
        raise BusinessProcessingError('Unable to create IOC for internal reasons')

    if not check_ioc_type_id(type_id=ioc.ioc_type_id):
        raise BusinessProcessingError('Not a valid IOC type')

    if case_iocs_db_exists(ioc):
        raise BusinessProcessingError('IOC with same value and type already exists')

    add_ioc(ioc, iris_current_user.id, ioc.case_id)

    ioc = call_modules_hook('on_postload_ioc_create', ioc, caseid=ioc.case_id)

    if ioc:
        track_activity(f'added ioc "{ioc.ioc_value}"', caseid=ioc.case_id)

        return ioc

    raise BusinessProcessingError('Unable to create IOC for internal reasons')


def iocs_update(ioc: Ioc, ioc_sc: Ioc) -> (Ioc, str):
    """
    Identifier: the IOC identifier
    Request JSON: the Request
    """
    try:
        ioc_sc.user_id = iris_current_user.id

        if not check_ioc_type_id(type_id=ioc_sc.ioc_type_id):
            raise BusinessProcessingError('Not a valid IOC type')

        update_ioc_state(ioc.case_id)
        add_obj_history_entry(ioc, 'updated ioc')
        db.session.commit()

        ioc_sc = call_modules_hook('on_postload_ioc_update', ioc_sc, caseid=ioc.case_id)

        if ioc_sc:
            track_activity(f'updated ioc "{ioc_sc.ioc_value}"', caseid=ioc.case_id)
            return ioc_sc

        raise BusinessProcessingError('Unable to update ioc for internal reasons')

    except Exception as e:
        raise BusinessProcessingError('Unexpected error server-side', e)


def iocs_delete(ioc: Ioc):
    call_modules_hook('on_preload_ioc_delete', ioc.ioc_id)

    delete_ioc(ioc)

    call_modules_hook('on_postload_ioc_delete', ioc.ioc_id, caseid=ioc.case_id)

    track_activity(f'deleted IOC "{ioc.ioc_value}"', caseid=ioc.case_id)
    return f'IOC {ioc.ioc_id} deleted'


def iocs_exports_to_json(case_id):
    iocs = get_iocs(case_id)

    return IocSchema().dump(iocs, many=True)


def iocs_build_filter_query(ioc_id: int = None,
                            ioc_uuid: str = None,
                            ioc_value: str = None,
                            ioc_type_id: int = None,
                            ioc_description: str = None,
                            ioc_tlp_id: int = None,
                            ioc_tags: str = None,
                            ioc_misp: str = None,
                            user_id: float = None):
    """
    Get a list of iocs from the database, filtered by the given parameters
    """
    conditions = []
    if ioc_id is not None:
        conditions.append(Ioc.ioc_id == ioc_id)
    if ioc_uuid is not None:
        conditions.append(Ioc.ioc_uuid == ioc_uuid)
    if ioc_value is not None:
        conditions.append(Ioc.ioc_value == ioc_value)
    if ioc_type_id is not None:
        conditions.append(Ioc.ioc_type_id == ioc_type_id)
    if ioc_description is not None:
        conditions.append(Ioc.ioc_description == ioc_description)
    if ioc_tlp_id is not None:
        conditions.append(Ioc.ioc_tlp_id == ioc_tlp_id)
    if ioc_tags is not None:
        conditions.append(Ioc.ioc_tags == ioc_tags)
    if ioc_misp is not None:
        conditions.append(Ioc.ioc_misp == ioc_misp)
    if user_id is not None:
        conditions.append(Ioc.user_id == user_id)

    return Ioc.query.filter(*conditions)


def iocs_filter(case_identifier, pagination_parameters, request_parameters):
    return get_filtered_iocs(case_identifier, pagination_parameters, request_parameters)
