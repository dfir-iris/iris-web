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

"""v2 endpoints for the Groups admin surface.

Extends the previously-thin CRUD to support the Access Control page:

  * paginated `GET /` with ILIKE search across group name + description
  * `GET /<id>/members` + `PUT /<id>/members` + `DELETE /<id>/members/<user_id>`
  * `GET /<id>/cases-access`
  * `POST /<id>/cases-access`   — supports `auto_follow_cases=true` or
                                  an explicit `cases_list`
  * `DELETE /<id>/cases-access` — bulk removal

Permission bitmask edits go through the existing `PUT /<id>` route
since they're a regular column on the Group model — no separate
endpoint needed.

All routes are gated on `Permissions.server_administrator` and
delegate to the existing legacy data + business helpers; no
duplication.
"""

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
from app.business.groups import groups_create
from app.business.groups import groups_delete
from app.business.groups import groups_get
from app.business.groups import groups_update
from app.datamgmt.manage.manage_groups_db import add_all_cases_access_to_group
from app.datamgmt.manage.manage_groups_db import add_case_access_to_group
from app.datamgmt.manage.manage_groups_db import get_group_details
from app.datamgmt.manage.manage_groups_db import get_group_with_members
from app.datamgmt.manage.manage_groups_db import remove_cases_access_from_group
from app.datamgmt.manage.manage_groups_db import remove_user_from_group
from app.datamgmt.manage.manage_groups_db import update_group_members
from app.datamgmt.manage.manage_users_db import get_user
from app.db import db
from app.iris_engine.access_control.utils import ac_ldp_group_removal
from app.iris_engine.access_control.utils import ac_ldp_group_update
from app.iris_engine.access_control.utils import ac_recompute_effective_ac_from_users_list
from app.models.authorization import Permissions
from app.models.authorization import ac_flag_match_mask
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.schema.marshables import AuthorizationGroupSchema


class Groups:

    def __init__(self):
        self._schema = AuthorizationGroupSchema()

    def search(self):
        """Paginated group list with ILIKE search.

        Search applies to name + description with OR semantics so the
        page can filter by either.
        """
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=25, type=int)
        per_page = max(1, min(per_page, 200))
        search = (request.args.get('search') or '').strip() or None

        from app.models.authorization import Group
        from sqlalchemy import or_
        query = Group.query
        if search:
            needle = f'%{search}%'
            query = query.filter(
                or_(Group.group_name.ilike(needle), Group.group_description.ilike(needle))
            )
        paginated = query.order_by(Group.group_id.asc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Hydrate `group_members` + `group_permissions_list` on each
        # row so the page can render the master list without a second
        # round-trip per row. `get_group_with_members` is the legacy
        # helper that attaches these.
        items = []
        for g in paginated.items:
            hydrated = get_group_with_members(g.group_id)
            if hydrated is not None:
                items.append(self._schema.dump(hydrated))
            else:
                items.append(self._schema.dump(g))

        return response_api_success({
            'total': paginated.total,
            'data': items,
            'last_page': paginated.pages,
            'current_page': paginated.page,
            'next_page': paginated.next_num if paginated.has_next else None,
        })

    def create(self):
        try:
            request_data = request.get_json()
            group = self._schema.load(request_data)
            group = groups_create(group)
            result = self._schema.dump(group)
            return response_api_created(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)

    def read(self, identifier):
        try:
            group = groups_get(identifier)
            # Re-hydrate with members + permission list so the editor
            # has everything it needs to render in one shot.
            hydrated = get_group_with_members(identifier) or group
            result = self._schema.dump(hydrated)
            return response_api_success(result)
        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, identifier):
        try:
            group = groups_get(identifier)
            request_data = request.get_json()
            request_data['group_id'] = identifier
            updated_group = self._schema.load(request_data, instance=group, partial=True)
            # Lock-out prevention copied from the legacy handler:
            # demoting the server-admin bit on a group the caller
            # belongs to would orphan their own admin access. The
            # backing helper checks group membership transitively.
            if 'group_permissions' in request_data and not ac_flag_match_mask(
                request_data['group_permissions'], Permissions.server_administrator.value
            ) and ac_ldp_group_update(iris_current_user.id):
                return response_api_error(
                    'That might not be a good idea Dave',
                    data='Updating the group permissions will lock you out',
                )
            groups_update()
            hydrated = get_group_with_members(identifier) or updated_group
            return response_api_success(self._schema.dump(hydrated))

        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)

        except ObjectNotFoundError:
            return response_api_not_found()

    def delete(self, identifier):
        try:
            group = groups_get(identifier)
            groups_delete(iris_current_user, group)
            return response_api_deleted()

        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())


groups_blueprint = Blueprint('rest_v2_groups', __name__, url_prefix='/groups')
groups = Groups()


@groups_blueprint.get('')
@ac_api_requires(Permissions.server_administrator)
def search_groups():
    return groups.search()


@groups_blueprint.post('')
@ac_api_requires(Permissions.server_administrator)
def create_group():
    return groups.create()


@groups_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def read_group(identifier):
    return groups.read(identifier)


@groups_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def update_group(identifier):
    return groups.update(identifier)


@groups_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def delete_group(identifier):
    return groups.delete(identifier)


# ---- Members ---------------------------------------------------------

def _require_group(group_id: int):
    """Internal: load with members + 404 if missing."""
    group = get_group_with_members(group_id)
    if group is None:
        return None, response_api_not_found()
    return group, None


@groups_blueprint.get('/<int:identifier>/members')
@ac_api_requires(Permissions.server_administrator)
def list_group_members(identifier: int) -> Response:
    group, err = _require_group(identifier)
    if err is not None:
        return err
    return response_api_success({'data': group.group_members})


@groups_blueprint.put('/<int:identifier>/members')
@ac_api_requires(Permissions.server_administrator)
def put_group_members(identifier: int) -> Response:
    """Replace the group's member list.

    Body: `{members: [user_id, ...]}` (or legacy `group_members`).
    The data-layer helper performs an in-place diff (remove orphans,
    insert newcomers, leave existing in place) so this isn't an
    O(N²) churn even with hundreds of users.
    """
    body = request.get_json() or {}
    members = body.get('members')
    if members is None:
        members = body.get('group_members')
    if not isinstance(members, list):
        return response_api_error('`members` must be a list of user IDs')
    for uid in members:
        if not isinstance(uid, int):
            return response_api_error(f'Invalid user id: {uid}')

    group, err = _require_group(identifier)
    if err is not None:
        return err

    update_group_members(group, members)
    refreshed = get_group_with_members(identifier)
    return response_api_success(AuthorizationGroupSchema().dump(refreshed))


@groups_blueprint.delete('/<int:identifier>/members/<int:user_id>')
@ac_api_requires(Permissions.server_administrator)
def remove_group_member(identifier: int, user_id: int) -> Response:
    """Drop a single user from the group.

    Refuses if the caller removing this user would lock the caller
    out — `ac_ldp_group_removal` does the transitive check.
    """
    group, err = _require_group(identifier)
    if err is not None:
        return err
    user = get_user(user_id)
    if user is None:
        return response_api_not_found()

    if ac_ldp_group_removal(user_id=user.id, group_id=group.group_id):
        return response_api_error(
            "I cannot let you do that Dave",
            data='Removing yourself from the group would lose your access rights',
        )

    remove_user_from_group(group, user)
    refreshed = get_group_with_members(identifier)
    return response_api_success(AuthorizationGroupSchema().dump(refreshed))


# ---- Group case access ----------------------------------------------

@groups_blueprint.get('/<int:identifier>/cases-access')
@ac_api_requires(Permissions.server_administrator)
def get_group_cases_access(identifier: int) -> Response:
    """List the group's per-case grants.

    The hydrated `Group` object exposes the rows under
    `group_cases_access`; we return the full projection so the page
    can render the picker without computing anything client-side.
    """
    group = get_group_details(identifier)
    if group is None:
        return response_api_not_found()
    return response_api_success(AuthorizationGroupSchema().dump(group))


@groups_blueprint.post('/<int:identifier>/cases-access')
@ac_api_requires(Permissions.server_administrator)
def add_group_cases_access(identifier: int) -> Response:
    """Grant the group access over cases.

    Body shape variants:
      * `{access_level, auto_follow_cases: true}` — grant access on
        every existing case and persist the auto-follow flag so
        future cases get the grant automatically.
      * `{access_level, cases_list: [int, ...]}` — explicit list.

    Either path triggers a recompute of effective access for every
    member of the group.
    """
    body = request.get_json() or {}

    access_level = body.get('access_level')
    if not isinstance(access_level, int):
        try:
            access_level = int(access_level)
        except (TypeError, ValueError):
            return response_api_error('`access_level` must be an int')

    auto_follow = bool(body.get('auto_follow_cases'))
    cases_list = body.get('cases_list')

    if not auto_follow and not isinstance(cases_list, list):
        return response_api_error('`cases_list` must be a list when `auto_follow_cases` is false')

    group, err = _require_group(identifier)
    if err is not None:
        return err

    if auto_follow:
        group, logs = add_all_cases_access_to_group(group, access_level)
        group.group_auto_follow = True
        group.group_auto_follow_access_level = access_level
        db.session.commit()
    else:
        group, logs = add_case_access_to_group(group, cases_list, access_level)
        group.group_auto_follow = False
        db.session.commit()

    if not group:
        return response_api_error(logs)

    refreshed = get_group_details(identifier)
    ac_recompute_effective_ac_from_users_list(refreshed.group_members)

    return response_api_success(AuthorizationGroupSchema().dump(refreshed))


@groups_blueprint.delete('/<int:identifier>/cases-access')
@ac_api_requires(Permissions.server_administrator)
def delete_group_cases_access(identifier: int) -> Response:
    """Drop the group's grants for `cases`.

    Body: `{cases: [int, ...]}`. Members' effective access is
    recomputed before the response returns so subsequent reads see
    the new state without a manual recompute call.
    """
    body = request.get_json() or {}
    cases = body.get('cases')
    if not isinstance(cases, list):
        return response_api_error('`cases` must be a list')

    group, err = _require_group(identifier)
    if err is not None:
        return err

    try:
        success, logs = remove_cases_access_from_group(group.group_id, cases)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return response_api_error(str(exc))

    if not success:
        return response_api_error(logs)

    ac_recompute_effective_ac_from_users_list(group.group_members)
    refreshed = get_group_details(identifier)
    return response_api_success(AuthorizationGroupSchema().dump(refreshed))
