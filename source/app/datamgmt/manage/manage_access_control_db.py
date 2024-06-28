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
from app import db, ac_current_user_has_permission
from app.models import Cases
from app.models.authorization import Group, UserClient, Permissions, CaseAccessLevel
from app.models.authorization import GroupCaseAccess
from app.models.authorization import Organisation
from app.models.authorization import OrganisationCaseAccess
from app.models.authorization import User
from app.models.authorization import UserCaseAccess


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


def check_ua_case_client(user_id: int, case_id: int) -> UserClient:
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
        uc = UserClient()
        uc.access_level = CaseAccessLevel.full_access.value
        return uc

    result = UserClient.query.filter(
        UserClient.user_id == user_id,
        Cases.case_id == case_id
    ).join(Cases,
           UserClient.client_id == Cases.client_id
    ).first()

    return result


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
    filters = []
    if not ac_current_user_has_permission(Permissions.server_administrator):
        filters.append(UserClient.user_id == user_id)

    result = UserClient.query.filter(
        *filters
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
