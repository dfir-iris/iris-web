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

import logging
from uuid import uuid4

from flask import session
from flask_login import current_user
from flask import request

from app.util import get_case_access
from app.iris_engine.access_control.utils import ac_get_effective_permissions_of_user
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.business.errors import PermissionDeniedError


def _deny_permission():
    error_uuid = uuid4()
    message = f'Permission denied (EID {error_uuid})'
    logging.warning(message)
    raise PermissionDeniedError(message)


# When moving down permission checks from the REST layer into the business layer,
# this method is used to replace manual calls to ac_fast_check_current_user_has_case_access
def check_current_user_has_some_case_access(case_identifier, access_levels):
    if not ac_fast_check_current_user_has_case_access(case_identifier, access_levels):
        _deny_permission()


# TODO: really this and the previous method should be merged.
#       This one comes from ac_api_case_requires, whereas the other one comes from the way api_delete_case was written...
# When moving down permission checks from the REST layer into the business layer,
# this method is used to replace annotation ac_api_case_requires
def check_current_user_has_some_case_access_stricter(access_levels):
    redir, caseid, has_access = get_case_access(request, access_levels, from_api=True)

    # TODO: do we really want to keep the details of the errors, when permission is denied => more work, more complex code?
    if not caseid or redir:
        _deny_permission()

    if not has_access:
        _deny_permission()


# When moving down permission checks from the REST layer into the business layer,
# this method is used to replace annotation ac_api_requires
def check_current_user_has_some_permission(permissions):
    if 'permissions' not in session:
        session['permissions'] = ac_get_effective_permissions_of_user(current_user)

    for permission in permissions:
        if session['permissions'] & permission.value:
            return

    _deny_permission()
