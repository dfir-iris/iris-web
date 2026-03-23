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

from app.db import db

from app.datamgmt.manage.manage_access_control_db import get_case_effective_access
from app.datamgmt.manage.manage_access_control_db import remove_duplicate_user_case_effective_accesses
from app.datamgmt.manage.manage_access_control_db import add_user_case_effective_access
from app.datamgmt.manage.manage_access_control_db import check_ua_case_client
from app.datamgmt.manage.manage_access_control_db import user_has_client_access
from app.logger import logger
from app.models.authorization import UserCaseAccess
from app.models.authorization import ac_has_permission_server_administrator
from app.models.authorization import CaseAccessLevel
from app.models.authorization import ac_flag_match_mask


def set_user_case_access(user_id, case_id, access_level):

    uca = UserCaseAccess.query.filter(
        UserCaseAccess.user_id == user_id,
        UserCaseAccess.case_id == case_id
    ).all()

    if len(uca) > 1:
        for u in uca:
            db.session.delete(u)
        db.session.commit()
        uca = None

    if not uca:
        uca = UserCaseAccess()
        uca.user_id = user_id
        uca.case_id = case_id
        uca.access_level = access_level
        db.session.add(uca)
    else:
        uca[0].access_level = access_level

    db.session.commit()

    set_case_effective_access_for_user(user_id, case_id, access_level)


def set_case_effective_access_for_user(user_id, case_id, access_level: int):
    """
    Set a case access from a user
    """

    if remove_duplicate_user_case_effective_accesses(user_id, case_id):
        logger.error(f'Multiple access found for user {user_id} and case {case_id}')

    add_user_case_effective_access(user_id, case_id, access_level)


def ac_fast_check_user_has_case_access(user_id, cid, expected_access_levels: list[CaseAccessLevel]):
    """
    Checks the user has access to the case with at least one of the access_level
    if the user has access, returns the access level of the user to the case
    Returns None otherwise
    """
    access_level = get_case_effective_access(user_id, cid)

    if not access_level:
        # The user has no direct access, check if he is part of the client
        access_level = check_ua_case_client(user_id, cid)
        if not access_level:
            return None
        set_case_effective_access_for_user(user_id, cid, access_level)

        return access_level

    if ac_flag_match_mask(access_level, CaseAccessLevel.deny_all.value):
        return None

    for acl in expected_access_levels:
        if ac_flag_match_mask(access_level, acl.value):
            return access_level

    return None


def access_controls_user_has_customer_access(user, permissions, customer_identifier):
    if ac_has_permission_server_administrator(permissions):
        return True

    user_id = getattr(user, 'id', None)
    if user_id is None:
        return False

    if user_has_client_access(user_id, customer_identifier):
        return True

    if hasattr(user, 'is_authenticated') or hasattr(user, 'user'):
        try:
            from app.blueprints.access_controls import ac_current_user_has_customer_access
            return ac_current_user_has_customer_access(customer_identifier)
        except Exception:
            return False

    return False
