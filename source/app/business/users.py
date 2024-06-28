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
from app import db
from app.business.errors import BusinessProcessingError
from app.datamgmt.manage.manage_users_db import get_user, get_active_user


def _reset_user_mfa(user_id: int = None):
    """
    Resets a user MFA by setting to none its MFA token
    """
    user = get_active_user(user_id=user_id)
    if user is None:
        raise BusinessProcessingError(f'User with id {user_id} is not found')

    user.mfa_secrets = None
    user.mfa_setup_complete = False

    db.session.commit()

