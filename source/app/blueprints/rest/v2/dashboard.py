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

from flask import Blueprint
from flask import request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_success
from app.business.cases import cases_filter_by_user
from app.business.cases import cases_filter_by_reviewer
from app.business.tasks import tasks_filter_by_user
from app.datamgmt.activities.activities_db import get_recent_activities_for_user
from app.datamgmt.activities.activities_db import get_recent_major_case_activities_for_user
from app.schema.marshables import CaseDetailsSchema
from app.schema.marshables import CaseSchema

dashboard_blueprint = Blueprint('dashboard',
                                __name__,
                                url_prefix='/dashboard')


# TODO this endpoint does not adhere to the conventions (verb in URL).
#      Prefer to use GET /api/v2/cases?case_owner_id=xx
@dashboard_blueprint.route('/cases/list', methods=['GET'])
@ac_api_requires()
def list_own_cases():
    show_closed = request.args.get('show_closed', 'false', type=str).lower()
    cases = cases_filter_by_user(iris_current_user, show_closed == 'true')

    return response_api_success(data=CaseDetailsSchema(many=True).dump(cases))


# TODO this endpoint does not adhere to the conventions (verb in URL).
#      We should rather have /api/v2/tasks?
@dashboard_blueprint.get('/tasks/list')
@ac_api_requires()
def list_own_tasks():
    # `tasks_filter_by_user` projects flat row tuples (task_id, task_title,
    # task_case, case_id, status_name, …), not model instances — running
    # those through CaseTaskSchema would silently drop the nested `case`
    # and `status` fields. Ship the rows as-is so the frontend sees the
    # case id, case title, status name, and last update.
    rows = tasks_filter_by_user()
    data = []
    for row in rows:
        d = row._asdict() if hasattr(row, '_asdict') else dict(row)
        if d.get('task_last_update') is not None:
            d['task_last_update'] = d['task_last_update'].isoformat()
        data.append(d)
    return response_api_success(data=data)


@dashboard_blueprint.get('/activities/recent')
@ac_api_requires()
def list_recent_activities():
    """Recent UI-visible activity entries the current user is allowed to
    see. Scoped to cases the user has access to (plus their own activity)
    so a multi-tenant deployment doesn't leak cross-customer events.

    Query params:
      - limit: int (default 20, max 100) — page size
      - offset: int (default 0)         — pagination cursor
    """
    limit = request.args.get('limit', default=20, type=int)
    if limit < 1:
        limit = 20
    if limit > 100:
        limit = 100

    offset = request.args.get('offset', default=0, type=int)
    if offset < 0:
        offset = 0

    rows = get_recent_activities_for_user(iris_current_user.id, limit=limit, offset=offset)
    # The DB query already projected the needed columns — no marshmallow
    # schema would add anything useful. Stamp dates as ISO strings and ship.
    data = []
    for row in rows:
        d = dict(row)
        if d.get('activity_date') is not None:
            d['activity_date'] = d['activity_date'].isoformat()
        data.append(d)

    return response_api_success(data=data)


@dashboard_blueprint.get('/activities/cases/major')
@ac_api_requires()
def list_recent_major_case_activities():
    """Recent major case activities (created / closed) for dashboard use.

    Query params:
      - limit: int (default 20, max 100) — page size
      - offset: int (default 0)         — pagination cursor
    """
    limit = request.args.get('limit', default=20, type=int)
    if limit < 1:
        limit = 20
    if limit > 100:
        limit = 100

    offset = request.args.get('offset', default=0, type=int)
    if offset < 0:
        offset = 0

    rows = get_recent_major_case_activities_for_user(iris_current_user.id, limit=limit, offset=offset)
    data = []
    for row in rows:
        d = dict(row)
        if d.get('activity_date') is not None:
            d['activity_date'] = d['activity_date'].isoformat()
        data.append(d)

    return response_api_success(data=data)


# TODO this endpoint does not adhere to the conventions (verb in URL).
#      We should rather have /api/v2/reviews?
@dashboard_blueprint.get('/reviews/list')
@ac_api_requires()
def list_own_reviews():
    reviews = cases_filter_by_reviewer(iris_current_user)
    return response_api_success(
        data=CaseSchema(
            many=True,
            only=["case_id", "case_name",
                  "review_status.status_name", "status_id"]
        ).dump(reviews))
