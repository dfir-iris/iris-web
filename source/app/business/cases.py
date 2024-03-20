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

from app import app
from app.models.authorization import CaseAccessLevel
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.datamgmt.manage.manage_cases_db import delete_case
from app.business.errors import BusinessProcessingError
from app.business.errors import PermissionDeniedError


def delete(identifier, context_case_identifier):
    if not ac_fast_check_current_user_has_case_access(identifier, [CaseAccessLevel.full_access]):
        raise PermissionDeniedError()

    if identifier == 1:
        track_activity(f'tried to delete case {identifier}, but case is the primary case',
                       caseid=context_case_identifier, ctx_less=True)

        raise BusinessProcessingError('Cannot delete a primary case to keep consistency')

    try:
        call_modules_hook('on_preload_case_delete', data=identifier, caseid=context_case_identifier)
        if not delete_case(identifier):
            track_activity(f'tried to delete case {identifier}, but it doesn\'t exist',
                           caseid=context_case_identifier, ctx_less=True)
            raise BusinessProcessingError('Tried to delete a non-existing case')
        call_modules_hook('on_postload_case_delete', data=identifier, caseid=context_case_identifier)
        track_activity(f'case {identifier} deleted successfully', ctx_less=True)
    except Exception as e:
        app.logger.exception(e)
        raise BusinessProcessingError('Cannot delete the case. Please check server logs for additional informations')
