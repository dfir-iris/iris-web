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

"""v2 endpoints for the Users admin surface.

Extends the previously-thin CRUD with the subresources the Access
Control page needs:

  * paginated `GET /` with ILIKE search across login + display name
  * `GET /<id>/groups` + `PUT /<id>/groups`         — group membership
  * `GET /<id>/customers` + `PUT /<id>/customers`    — customer access
  * `GET /<id>/cases-access`                         — list explicit cases
  * `POST /<id>/cases-access` / `DELETE /<id>/cases-access` — bulk edit
  * `POST /<id>/activate` / `POST /<id>/deactivate`
  * `POST /<id>/api-key/renew`
  * `POST /<id>/mfa/reset`
  * `POST /<id>/recompute-access`
  * `GET /<id>/audit`                                — effective access trace

All routes are gated on `Permissions.server_administrator`. The
implementations delegate to the existing legacy data + business
helpers — no duplication, just thin v2 wrappers.
"""

import secrets
from typing import Any
from typing import Dict
from typing import List

from flask import Blueprint
from flask import Response
from flask import request
from marshmallow import ValidationError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.business.users import users_create
from app.business.users import users_delete
from app.business.users import users_get
from app.business.users import users_reset_mfa
from app.business.users import users_update
from app.business.groups import groups_exist
from app.datamgmt.manage.manage_users_db import add_case_access_to_user
from app.datamgmt.manage.manage_users_db import get_filtered_users
from app.datamgmt.manage.manage_users_db import get_user
from app.datamgmt.manage.manage_users_db import get_user_details
from app.datamgmt.manage.manage_users_db import remove_cases_access_from_user
from app.datamgmt.manage.manage_users_db import update_user_customers
from app.datamgmt.manage.manage_users_db import update_user_groups
from app.db import db
from app.iris_engine.access_control.utils import ac_recompute_effective_ac
from app.iris_engine.access_control.utils import ac_trace_effective_user_permissions
from app.iris_engine.access_control.utils import ac_trace_user_effective_cases_access_2
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.schema.marshables import UserSchemaForAPIV2


# Allowlist of fields an administrator may write when creating or updating a
# user via the v2 admin endpoints. Anything else the caller tries to sneak in
# (uuid, mfa_secrets, webauthn_credentials, mfa_setup_complete, api_key,
# external_id, ...) is silently dropped before the schema is loaded. Closes
# the mass-assignment vector reported as GHSA-w78h-mx7h-qm3h /
# SBA-ADV-20260128-01 / CWE-915.
_ADMIN_USER_WRITABLE_FIELDS = {
    'user_id',
    'user_active',
    'user_name',
    'user_login',
    'user_email',
    'user_password',
    'user_isadmin',
    'user_is_service_account',
    'user_primary_organisation_id',
    'user_roles_str',
}


def _filter_admin_user_payload(data):
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k in _ADMIN_USER_WRITABLE_FIELDS}


class Users:

    def __init__(self):
        self._schema = UserSchemaForAPIV2()

    def search(self):
        """Paginated user list with ILIKE search on login + display name.

        Search applies to either column with an OR so admins can find
        someone by typing either the friendly name or the login slug.
        """
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=25, type=int)
        per_page = max(1, min(per_page, 200))
        search = (request.args.get('search') or '').strip() or None

        # `get_filtered_users` accepts user_name + user_login as
        # independent ILIKE filters; calling it twice would be ugly so
        # we pass the same needle as both and ORM_collapses them via
        # the function's existing `and_` reduction. To preserve OR
        # semantics we instead query manually here.
        from app.models.authorization import User
        from sqlalchemy import or_
        query = User.query
        if search:
            needle = f'%{search}%'
            query = query.filter(or_(User.name.ilike(needle), User.user.ilike(needle)))
        paginated = query.order_by(User.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return response_api_success({
            'total': paginated.total,
            'data': [self._schema.dump(u) for u in paginated.items],
            'last_page': paginated.pages,
            'current_page': paginated.page,
            'next_page': paginated.next_num if paginated.has_next else None,
        })

    def create(self):
        try:
            request_data = _filter_admin_user_payload(request.get_json())
            request_data['user_id'] = 0
            request_data['user_active'] = request_data.get('user_active', True)
            user = self._schema.load(request_data)
            user = users_create(user, request_data['user_active'])
            result = self._schema.dump(user)
            return response_api_created(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)

    def read(self, identifier):
        try:
            user = users_get(identifier)
            result = self._schema.dump(user)
            return response_api_success(result)
        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, identifier):

        try:
            user = users_get(identifier)
            request_data = _filter_admin_user_payload(request.get_json())
            request_data['user_id'] = identifier
            new_user = self._schema.load(request_data, instance=user, partial=True)
            user_updated = users_update(new_user, request_data.get('user_password'))
            result = self._schema.dump(user_updated)
            return response_api_success(result)

        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)

        except ObjectNotFoundError:
            return response_api_not_found()

    def delete(self, identifier):
        try:
            user = users_get(identifier)
            users_delete(user)
            return response_api_deleted()

        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())


users = Users()
users_blueprint = Blueprint('users_rest_v2', __name__, url_prefix='/users')


@users_blueprint.get('')
@ac_api_requires(Permissions.server_administrator)
def search_users():
    return users.search()


@users_blueprint.post('')
@ac_api_requires(Permissions.server_administrator)
def create_user():
    return users.create()


@users_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def get_user_endpoint(identifier):
    return users.read(identifier)


@users_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def put_user(identifier):
    return users.update(identifier)


@users_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def delete_user(identifier):
    return users.delete(identifier)


# ---- Subresources ----------------------------------------------------

def _require_user(user_id: int):
    """Internal: load + 404 if missing."""
    user = get_user(user_id)
    if user is None:
        return None, response_api_not_found()
    return user, None


@users_blueprint.get('/<int:identifier>/groups')
@ac_api_requires(Permissions.server_administrator)
def list_user_groups(identifier: int) -> Response:
    """Return the user's group membership as a list of `{id, name}`.

    Powers the "Groups" tab on the User edit modal and the membership
    picker. We don't add a "groups available to add" sub-endpoint
    here — the page already loads the full group list elsewhere.
    """
    user, err = _require_user(identifier)
    if err is not None:
        return err
    return response_api_success({
        'data': [
            {'group_id': g.group_id, 'group_name': g.group_name}
            for g in user.groups
        ]
    })


@users_blueprint.put('/<int:identifier>/groups')
@ac_api_requires(Permissions.server_administrator)
def put_user_groups(identifier: int) -> Response:
    """Replace the user's group membership.

    Body: `{groups: [int, ...]}`. Each group id is validated to exist
    before any DB write. Matches the legacy "groups_membership" key
    by also accepting that for back-compat.
    """
    body = request.get_json() or {}
    groups = body.get('groups')
    if groups is None:
        groups = body.get('groups_membership')
    if not isinstance(groups, list):
        return response_api_error('`groups` must be a list of group IDs')

    user, err = _require_user(identifier)
    if err is not None:
        return err

    for gid in groups:
        if not isinstance(gid, int) or not groups_exist(gid):
            return response_api_error(f'Unknown group id: {gid}')

    update_user_groups(identifier, groups)
    track_activity(f'groups membership of user {identifier} updated', ctx_less=True)
    return response_api_success(get_user_details(identifier))


@users_blueprint.put('/<int:identifier>/customers')
@ac_api_requires(Permissions.server_administrator)
def put_user_customers(identifier: int) -> Response:
    """Replace the user's customer membership.

    Body: `{customers: [int, ...]}`. The data-layer call mirrors the
    legacy `update_user_customers`; here we just normalise the body.
    """
    body = request.get_json() or {}
    customers = body.get('customers')
    if customers is None:
        customers = body.get('customers_membership')
    if not isinstance(customers, list):
        return response_api_error('`customers` must be a list of customer IDs')
    for cid in customers:
        if not isinstance(cid, int):
            return response_api_error(f'Invalid customer id: {cid}')

    user, err = _require_user(identifier)
    if err is not None:
        return err

    update_user_customers(user_id=identifier, customers=customers)
    track_activity(f'customers membership of user {identifier} updated', ctx_less=True)
    return response_api_success(get_user_details(identifier))


@users_blueprint.get('/<int:identifier>/cases-access')
@ac_api_requires(Permissions.server_administrator)
def get_user_cases_access(identifier: int) -> Response:
    """List the user's *explicit* per-case access rows.

    Effective access (after merging group / org grants) is exposed
    by the audit endpoint below — this one shows just what the admin
    can directly edit.
    """
    details = get_user_details(user_id=identifier)
    if details is None:
        return response_api_not_found()
    # `get_user_details` returns v2-shaped keys; fall back to the
    # legacy key the older serialiser used.
    cases_access = details.get('user_cases_access', details.get('cases_access', []))
    return response_api_success({'data': cases_access})


@users_blueprint.post('/<int:identifier>/cases-access')
@ac_api_requires(Permissions.server_administrator)
def add_user_cases_access(identifier: int) -> Response:
    """Grant `access_level` over `cases_list` to the user.

    Body: `{cases_list: [int, ...], access_level: int}`. Existing
    grants for the same case are overwritten in place — the
    underlying helper handles both insert + update.
    """
    body = request.get_json() or {}
    cases_list = body.get('cases_list')
    access_level = body.get('access_level')
    if not isinstance(cases_list, list):
        return response_api_error('`cases_list` must be a list')
    if not isinstance(access_level, int):
        try:
            access_level = int(access_level)
        except (TypeError, ValueError):
            return response_api_error('`access_level` must be an int')

    user, err = _require_user(identifier)
    if err is not None:
        return err

    user, logs = add_case_access_to_user(user, cases_list, access_level)
    if not user:
        return response_api_error(logs)

    track_activity(
        f'case access level {access_level} for case(s) {cases_list} set for user {user.user}',
        ctx_less=True,
    )
    return response_api_success(get_user_details(identifier))


@users_blueprint.delete('/<int:identifier>/cases-access')
@ac_api_requires(Permissions.server_administrator)
def delete_user_cases_access(identifier: int) -> Response:
    """Drop explicit case grants for `cases`.

    Body: `{cases: [int, ...]}`. DELETE with a body is unusual but
    intentional: removing a list of grants is conceptually a single
    bulk operation and forcing it through GET-with-query or POST
    would be even noisier.
    """
    body = request.get_json() or {}
    cases = body.get('cases')
    if not isinstance(cases, list):
        return response_api_error('`cases` must be a list')

    user, err = _require_user(identifier)
    if err is not None:
        return err

    try:
        success, logs = remove_cases_access_from_user(user.id, cases)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return response_api_error(str(exc))

    if not success:
        return response_api_error(logs)

    track_activity(
        f'cases access for case(s) {cases} deleted for user {user.user}',
        ctx_less=True,
    )
    return response_api_success(get_user_details(identifier))


@users_blueprint.post('/<int:identifier>/activate')
@ac_api_requires(Permissions.server_administrator)
def activate_user(identifier: int) -> Response:
    user, err = _require_user(identifier)
    if err is not None:
        return err
    user.active = True
    db.session.commit()
    track_activity(f'user {user.user} activated', ctx_less=True)
    return response_api_success(Users()._schema.dump(user))


@users_blueprint.post('/<int:identifier>/deactivate')
@ac_api_requires(Permissions.server_administrator)
def deactivate_user(identifier: int) -> Response:
    """Disable a user account.

    Refuses if the caller is trying to deactivate themselves — the
    legacy route had the same guard and it's worth keeping; an admin
    locking themselves out is irrecoverable without DB access.
    """
    if iris_current_user.id == identifier:
        return response_api_error(
            'Refusing to deactivate yourself — you would lock yourself out.'
        )
    user, err = _require_user(identifier)
    if err is not None:
        return err
    user.active = False
    db.session.commit()
    track_activity(f'user {user.user} deactivated', ctx_less=True)
    return response_api_success(Users()._schema.dump(user))


@users_blueprint.post('/<int:identifier>/api-key/renew')
@ac_api_requires(Permissions.server_administrator)
def renew_user_api_key(identifier: int) -> Response:
    """Rotate the user's API key. Returns the *new* key in the body
    once — the admin should copy it immediately; we don't surface it
    again on subsequent reads."""
    user, err = _require_user(identifier)
    if err is not None:
        return err
    new_key = secrets.token_urlsafe(nbytes=64)
    user.api_key = new_key
    db.session.commit()
    track_activity(f'API key of user {user.user} renewed', ctx_less=True)
    return response_api_success({
        'user_id': user.id,
        'user': user.user,
        'api_key': new_key,
    })


@users_blueprint.post('/<int:identifier>/mfa/reset')
@ac_api_requires(Permissions.server_administrator)
def reset_user_mfa(identifier: int) -> Response:
    """Clear MFA secrets for the user. The underlying business
    helper raises `BusinessProcessingError` when the user can't be
    found (rather than a typed not-found) — surface both paths
    cleanly."""
    try:
        users_reset_mfa(identifier)
    except BusinessProcessingError as exc:
        return response_api_error(exc.get_message())
    track_activity(f'MFA reset for user #{identifier}', ctx_less=True)
    return response_api_success({'message': 'MFA reset'})


@users_blueprint.post('/<int:identifier>/recompute-access')
@ac_api_requires(Permissions.server_administrator)
def recompute_user_access(identifier: int) -> Response:
    """Force-recompute the user's effective case access cache.

    Useful after a manual DB poke or to debug effective-access
    drift. The legacy UI exposed this on the User Audit modal.
    """
    user, err = _require_user(identifier)
    if err is not None:
        return err
    ac_recompute_effective_ac(identifier)
    return response_api_success({'message': 'Recomputed'})


@users_blueprint.get('/<int:identifier>/audit')
@ac_api_requires(Permissions.server_administrator)
def audit_user(identifier: int) -> Response:
    """Effective-access trace.

    Returns:
      * `access_audit`: per-case rows showing where the user's
        effective access came from (direct user grant, group, org).
      * `permissions_audit`: per-permission rows showing which
        group(s) contribute each bit of the user's effective
        permission bitmask.

    Both projections are computed on-the-fly by the iris_engine
    helpers; nothing is persisted.
    """
    user, err = _require_user(identifier)
    if err is not None:
        return err
    return response_api_success({
        'access_audit': ac_trace_user_effective_cases_access_2(identifier),
        'permissions_audit': ac_trace_effective_user_permissions(identifier),
    })


# Keep linter quiet about unused imports referenced indirectly.
_ = (Any, Dict, List)
