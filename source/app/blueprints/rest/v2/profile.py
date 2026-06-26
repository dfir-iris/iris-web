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

import secrets
from flask import Blueprint
from flask import current_app
from flask import request
from flask import session
from marshmallow import ValidationError

from app import bc
from app.db import db
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.access_controls import ac_api_requires
from app.business.users import users_get
from app.business.users import users_update
from app.iris_engine.access_control.utils import ac_get_effective_permissions_of_user
from app.iris_engine.access_control.utils import ac_recompute_effective_ac
from app.models.authorization import Permissions
from app.schema.marshables import UserSchemaForAPIV2


class ProfileOperations:

    def __init__(self):
        self._schema = UserSchemaForAPIV2()
        self._update_request_schema = UserSchemaForAPIV2(exclude=['user_is_service_account', 'user_active', 'uuid'])

    def get(self):
        user = users_get(iris_current_user.id)
        result = self._schema.dump(user)
        return response_api_success(result)

    def update(self):
        try:
            user = users_get(iris_current_user.id)
            # Self-service profile updates expose only a password change in
            # the GUI. Restricting the payload to that one field stops any
            # client from sneaking attributes the schema would otherwise
            # accept (user_login, user_email, user_isadmin, user_name, ...)
            # and overwriting the user's own row — the mass-assignment
            # vector reported as GHSA-w78h-mx7h-qm3h / SBA-ADV-20260128-01 /
            # CWE-915. `user_current_password` is not a model field and is
            # popped off before the schema sees the payload.
            raw = request.get_json()
            if not isinstance(raw, dict):
                raw = {}
            new_password = raw.get('user_password')
            current_password = raw.get('user_current_password')

            if new_password:
                if not current_password:
                    return response_api_error(
                        'Current password is required to change password',
                        data={'user_current_password': ['Required field']}
                    )
                if not bc.check_password_hash(user.password, current_password):
                    return response_api_error(
                        'Current password is incorrect',
                        data={'user_current_password': ['Incorrect password']}
                    )

            request_data = {
                'user_password': new_password,
                'user_id': iris_current_user.id,
            }

            user = self._update_request_schema.load(request_data, instance=user, partial=True)
            user = users_update(user, new_password)
            result = self._schema.dump(user)
            return response_api_success(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)

    def renew_api_key(self):
        user = users_get(iris_current_user.id)
        user.api_key = secrets.token_urlsafe(nbytes=64)
        db.session.commit()
        result = self._schema.dump(user)
        return response_api_success(result)

    def refresh_permissions(self):
        user = users_get(iris_current_user.id)
        ac_recompute_effective_ac(iris_current_user.id)
        session['permissions'] = ac_get_effective_permissions_of_user(user)
        result = self._schema.dump(user)
        return response_api_success(result)

    def get_context(self):
        """Compact bootstrap payload the SPA needs on every load.

        Returns the running IRIS version, the demo-mode flag, and the
        effective permission mask + matching enum names for the current
        user. The SPA uses this to render the version strip in the side
        bar and to gate menu entries the user isn't allowed to reach.

        Kept lightweight on purpose: no DB writes, no joins beyond what
        `ac_get_effective_permissions_of_user` already does. Any
        authenticated user can call it — this is *their own* context.
        """
        user = users_get(iris_current_user.id)
        mask = ac_get_effective_permissions_of_user(user)
        # `standard_user` is implicit for every authenticated user, even
        # if the group bitmask doesn't include it (admins, service
        # accounts). Include it so the SPA can treat it as a baseline.
        if user is not None:
            mask |= Permissions.standard_user.value
        names = [p.name for p in Permissions if (mask & p.value) == p.value]

        demo_mode = current_app.config.get('DEMO_MODE_ENABLED') == 'True'

        return response_api_success({
            'iris_version': current_app.config.get('IRIS_VERSION'),
            'demo_mode': demo_mode,
            'permissions': {
                'mask': mask,
                'names': names,
            },
        })


profile_operations = ProfileOperations()
profile_blueprint = Blueprint('profile_rest_v2', __name__, url_prefix='/me')


@profile_blueprint.get('')
@ac_api_requires()
def get_profile():
    return profile_operations.get()


@profile_blueprint.put('')
@ac_api_requires()
def update_profile():
    return profile_operations.update()


@profile_blueprint.post('/api-key/renew')
@ac_api_requires()
def renew_api_key():
    return profile_operations.renew_api_key()


@profile_blueprint.post('/permissions/refresh')
@ac_api_requires()
def refresh_permissions():
    return profile_operations.refresh_permissions()


@profile_blueprint.get('/context')
@ac_api_requires()
def get_context():
    return profile_operations.get_context()
