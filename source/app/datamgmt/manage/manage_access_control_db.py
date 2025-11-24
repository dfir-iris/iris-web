#  IRIS Source Code
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
from sqlalchemy import and_

from app import ac_current_user_has_permission
from app import db
from app.models.cases import Cases
from app.models.authorization import Group
from app.models.authorization import UserClient
from app.models.authorization import UserCaseEffectiveAccess
from app.models.authorization import Permissions
from app.models.authorization import CaseAccessLevel
from app.models.authorization import GroupCaseAccess
from app.models.authorization import Organisation
from app.models.authorization import OrganisationCaseAccess
from app.models.authorization import User
from app.models.authorization import UserCaseAccess

from typing import Optional
from app.logger import logger


def manage_ac_audit_users_db():
    uca = UserCaseAccess.query.with_entities(
        User.name,
        User.user,
        User.id,
        User.uuid,
        UserCaseAccess.access_level,
        Cases.name,
        Cases.case_id
    ).join(
        UserCaseAccess.case
    ).join(
        UserCaseAccess.user
    ).all()

    gca = GroupCaseAccess.query.with_entities(
        Group.group_name,
        Group.group_id,
        Group.group_uuid,
        GroupCaseAccess.access_level,
        Cases.name,
        Cases.case_id
    ).join(
        GroupCaseAccess.case
    ).join(
        GroupCaseAccess.group
    ).all()

    oca = OrganisationCaseAccess.query.with_entities(
        Organisation.org_name,
        Organisation.org_id,
        Organisation.org_uuid,
        OrganisationCaseAccess.access_level,
        Cases.name,
        Cases.case_id
    ).all()

    ret = {
        'users': [u._asdict() for u in uca],
        'groups': [g._asdict() for g in gca],
        'organisations': [o._asdict() for o in oca]
    }

    return ret


def check_ua_case_client(user_id: int, case_id: int) -> Optional[int]:
    """Check if the user has access to the case, through the customer of the case
       (in other words, check that the customer of the case is assigned to the user)

    Args:
        user_id (int): identifier of the user
        case_id (int): identifier of the case

    Returns:
        UserClient: the user relationship with the customer of the case, if it is assigned to the user
                    None otherwise
    """
    if ac_current_user_has_permission(Permissions.server_administrator):
        # Return a dummy object
        return CaseAccessLevel.full_access.value

    result = UserClient.query.filter(
        UserClient.user_id == user_id,
        Cases.case_id == case_id
    ).join(
        Cases,
        UserClient.client_id == Cases.client_id
    ).first()

    if not result:
        return None

    return result.access_level


def get_case_effective_access(user_identifier, case_identifier) -> Optional[int]:
    row = UserCaseEffectiveAccess.query.with_entities(
        UserCaseEffectiveAccess.access_level
    ).filter(
        UserCaseEffectiveAccess.user_id == user_identifier,
        UserCaseEffectiveAccess.case_id == case_identifier
    ).first()

    if not row:
        return None

    return row[0]


def get_client_users(client_id: int) -> list:
    """Get users for a client

    Args:
        client_id (int): Client ID

    Returns:
        list: List of users
    """
    result = UserClient.query.filter(
        UserClient.client_id == client_id
    ).all()

    return result


def get_user_clients_id(user_id: int) -> list:
    """Get clients for a user

    Args:
        user_id (int): User ID

    Returns:
        list: List of clients
    """
    result = UserClient.query.filter(
        UserClient.user_id == user_id
    ).with_entities(
        UserClient.client_id
    ).all()

    return [r[0] for r in result]


def user_has_client_access(user_id: int, client_id: int) -> bool:
    """Check if a user has access to a client

    Args:
        user_id (int): User ID
        client_id (int): Client ID

    Returns:
        bool: True if the user has access to the client
    """
    if ac_current_user_has_permission(Permissions.server_administrator):
        return True

    result = UserClient.query.filter(
        UserClient.user_id == user_id,
        UserClient.client_id == client_id
    ).first()

    return result is not None


def remove_duplicate_user_case_effective_accesses(user_id, case_id):
    uac = UserCaseEffectiveAccess.query.where(and_(
        UserCaseEffectiveAccess.user_id == user_id,
        UserCaseEffectiveAccess.case_id == case_id
    )).all()

    if len(uac) <= 1:
        return False

    for u in uac[1:]:
        db.session.delete(u)
    db.session.commit()
    return True


def set_user_case_effective_access(access_level, case_id, user_id):
    # Validate case_id is not None
    if case_id is None:
        logger.error(f'Attempted to set access for user {user_id} with NULL case_id')
        return
    
    # Validate the case exists before creating access record
    from app.models.cases import Cases
    case_exists = Cases.query.filter(Cases.case_id == case_id).first()
    if not case_exists:
        logger.error(f'Attempted to set access for user {user_id} to non-existent case {case_id}')
        return
    
    uac = UserCaseEffectiveAccess.query.where(and_(
        UserCaseEffectiveAccess.user_id == user_id,
        UserCaseEffectiveAccess.case_id == case_id
    )).first()
    if uac:
        uac.access_level = access_level
    else:
        # Create new effective access entry if it doesn't exist
        uac = UserCaseEffectiveAccess()
        uac.user_id = user_id
        uac.case_id = case_id
        uac.access_level = access_level
        db.session.add(uac)
    db.session.commit()


def cleanup_orphaned_case_access_records():
    """
    Remove access records for cases that no longer exist
    """
    # Find all orphaned records where case_id is NULL or references non-existent cases
    orphaned = UserCaseEffectiveAccess.query.outerjoin(
        Cases, UserCaseEffectiveAccess.case_id == Cases.case_id
    ).filter(
        Cases.case_id.is_(None)
    ).all()
    
    count = len(orphaned)
    if count > 0:
        for record in orphaned:
            db.session.delete(record)
        db.session.commit()
        logger.info(f'Cleaned up {count} orphaned case access records')
    
    return count
