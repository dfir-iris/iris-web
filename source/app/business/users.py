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
from app.models.authorization import User
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.datamgmt.manage.manage_users_db import get_active_user
from app.datamgmt.manage.manage_users_db import get_user_details_return_user
from app.datamgmt.manage.manage_users_db import get_active_user_by_login
from app.datamgmt.manage.manage_users_db import create_user
from app.datamgmt.manage.manage_users_db import update_user
from app.datamgmt.manage.manage_users_db import delete_user
from app.datamgmt.manage.manage_users_db import get_user_organisations
from app.datamgmt.manage.manage_users_db import get_user_primary_org
from app.datamgmt.comments import user_has_comments
from app.iris_engine.utils.tracker import track_activity


def users_reset_mfa(user_id: int = None):
    """
    Resets a user MFA by setting to none its MFA token
    """
    user = get_active_user(user_id=user_id)
    if user is None:
        raise BusinessProcessingError(f'User with id {user_id} is not found')

    user.mfa_secrets = None
    user.mfa_setup_complete = False

    db.session.commit()


def retrieve_user_by_username(username: str):
    """
    Retrieve the user object by username.

    :param username: Username
    :return: User object if found, None
    """
    user = get_active_user_by_login(username)
    if not user:
        track_activity(f'someone tried to log in with user "{username}", which does not exist',
                       ctx_less=True, display_in_ui=False)
    return user


def users_create(user: User, active) -> User:
    user = create_user(user.name,
                       user.user,
                       user.password,
                       user.email,
                       active,
                       user_is_service_account=user.is_service_account)

    track_activity(f'created user {user.user}', ctx_less=True)
    return user


def users_get(identifier) -> User:
    user = get_user_details_return_user(identifier)
    if not user:
        raise ObjectNotFoundError()
    return user


def users_get_active(user_id) -> User:
    user = get_active_user(user_id)
    if not user:
        raise ObjectNotFoundError
    return user


def users_update(user: User, user_password: str) -> User:
    user = update_user(user, password=user_password)
    track_activity(f'updated user {user.user}', ctx_less=True)
    return user


def users_delete(user: User):
    if user.active:
        raise BusinessProcessingError('Cannot delete active user')
    if user_has_comments(user):
        raise BusinessProcessingError('Cannot delete user with associated comments')
    delete_user(user.id)
    track_activity(message=f'deleted user ID {user.id}', ctx_less=True)


def get_primary_organisation(user_id):
    uoe = get_user_primary_org(user_id)
    if not uoe:
        return 0
    return uoe.org_id


def get_organisations(user_id):
    return get_user_organisations(user_id)
