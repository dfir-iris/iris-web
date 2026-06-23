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

from flask import Blueprint
from flask import request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_current_user_has_permission
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_success
from app.business.activity import list_activities
from app.models.authorization import Permissions


activities_blueprint = Blueprint('activities_rest_v2', __name__, url_prefix='/activities')


def _format_row(row):
    # Same projection shape as the legacy /activities/list endpoint, but
    # with ``activity_date`` serialised as an ISO string (no Marshmallow
    # schema — every column is already a primitive after `with_entities`).
    d = row._asdict() if hasattr(row, '_asdict') else dict(row)
    if d.get('activity_date') is not None:
        d['activity_date'] = d['activity_date'].isoformat()
    return d


@activities_blueprint.get('')
@ac_api_requires(Permissions.activities_read, Permissions.all_activities_read)
def list_activities_endpoint():
    """Paginated, access-scoped listing of UserActivity rows.

    Query params:
      - page (int, default 1)
      - per_page (int, default 25, max 200)
      - search (str, optional) — ILIKE filter on activity_desc
      - include_non_case (bool, default false) — include rows with no
        associated case. Only honoured when the caller has the
        ``all_activities_read`` permission (otherwise non-case rows from
        other users would leak across tenants).
      - user_id (int, optional) — restrict to a single author
      - case_id (int, optional) — restrict to a single case
    """
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=25, type=int)
    search_value = request.args.get('search', default=None, type=str)
    user_id = request.args.get('user_id', default=None, type=int)
    case_id = request.args.get('case_id', default=None, type=int)

    raw_include = (request.args.get('include_non_case') or '').strip().lower()
    include_non_case = raw_include in ('1', 'true', 'yes', 'on')

    # `case_ids` and `user_ids` accept the same flexible shapes the rest
    # of the v2 API uses: comma-separated `?case_ids=1,2,3` and/or
    # repeated `?case_ids=1&case_ids=2`. Non-integer pieces are dropped
    # silently rather than 400'ing — keeps URL-state hydration robust.
    def _int_list(name):
        raw = request.args.getlist(name) or []
        out = []
        for r in raw:
            for piece in r.split(','):
                piece = piece.strip()
                if not piece:
                    continue
                try:
                    out.append(int(piece))
                except ValueError:
                    continue
        return out or None

    case_ids = _int_list('case_ids')
    user_ids = _int_list('user_ids')

    # Optional date window. We accept anything `datetime.fromisoformat`
    # understands (YYYY-MM-DD or full ISO with offset). Bad inputs are
    # ignored — same robustness principle as the int-list parser above.
    from datetime import datetime

    def _iso(name):
        raw = request.args.get(name)
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    date_from = _iso('date_from')
    date_to = _iso('date_to')

    def _tribool(name):
        raw = (request.args.get(name) or '').strip().lower()
        if raw in ('1', 'true', 'yes', 'on'):
            return True
        if raw in ('0', 'false', 'no', 'off'):
            return False
        return None

    is_from_api = _tribool('is_from_api')
    is_manual = _tribool('is_manual')

    can_read_all = ac_current_user_has_permission(Permissions.all_activities_read)
    # `include_non_case` only matters for the global "admin" view —
    # outside that view it would surface rows from cases the caller can't
    # otherwise see.
    if not can_read_all:
        include_non_case = False

    paginated = list_activities(
        user_id=iris_current_user.id,
        can_read_all=can_read_all,
        page=page,
        per_page=per_page,
        include_non_case=include_non_case,
        search_value=search_value,
        scope_user_id=user_id,
        case_id=case_id,
        user_ids=user_ids,
        case_ids=case_ids,
        date_from=date_from,
        date_to=date_to,
        is_from_api=is_from_api,
        is_manual=is_manual,
    )

    # We project ourselves rather than going through `response_api_paginated`
    # because that helper expects a Marshmallow schema. The rows are already
    # flat dicts of primitives.
    return response_api_success(data={
        'total': paginated.total,
        'data': [_format_row(r) for r in paginated.items],
        'last_page': paginated.pages,
        'current_page': paginated.page,
        'next_page': paginated.next_num if paginated.has_next else None,
    })
