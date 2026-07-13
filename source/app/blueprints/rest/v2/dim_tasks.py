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
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.business.asynchronous_tasks import asynchronous_task_get_by_id
from app.business.asynchronous_tasks import asynchronous_tasks_list
from app.business.asynchronous_tasks import dim_tasks_get


dim_tasks_blueprint = Blueprint('dim_tasks_rest_v2', __name__, url_prefix='/dim-tasks')


@dim_tasks_blueprint.get('')
@ac_api_requires()
def list_dim_tasks_endpoint():
    """Paginated listing of Celery (Dim) tasks.

    Query params:
      - page (int, default 1)
      - per_page (int, default 25, clamped to 1..200)
      - search (str, optional) — ILIKE filter over task name + task id
      - status (str, optional) — exact-match on the Celery status column
        (SUCCESS / FAILURE / PENDING / STARTED / RETRY).
    """
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=25, type=int)
    # Clamp here so a hostile caller can't ask for 100k rows.
    per_page = max(1, min(per_page, 200))

    search_value = (request.args.get('search') or '').strip() or None
    status = (request.args.get('status') or '').strip() or None

    items, paginated = asynchronous_tasks_list(
        page=page,
        per_page=per_page,
        search_value=search_value,
        status=status,
    )

    return response_api_success(data={
        'total': paginated.total,
        'data': items,
        'last_page': paginated.pages,
        'current_page': paginated.page,
        'next_page': paginated.next_num if paginated.has_next else None,
    })


@dim_tasks_blueprint.get('/<task_id>')
@ac_api_requires()
def get_dim_task_endpoint(task_id):
    """Detail view for a single Dim task.

    Returns the full Celery AsyncResult metadata (logs, traceback, etc.)
    plus the row-shape projection used by the listing — handy because
    the frontend can hydrate a slide-out panel without a second request.

    404 only if the meta row itself is missing. A successful AsyncResult
    fetch for an unknown id still returns a "PENDING" stub from Celery,
    so we use the DB lookup as the source of truth for existence.
    """
    projected = asynchronous_task_get_by_id(task_id)
    if projected is None:
        return response_api_not_found()

    # `dim_tasks_get` does the heavy lifting (unpickling task.info,
    # parsing logs/traceback). Keys are human-readable strings — keep
    # them as-is so the frontend can render them verbatim in a key/value
    # detail card.
    details = dim_tasks_get(task_id)

    # `Task finished on` is a Python datetime — serialise to ISO so JSON
    # round-trips cleanly. Other values are already primitives.
    finished_on = details.get('Task finished on')
    if finished_on is not None and hasattr(finished_on, 'isoformat'):
        details = {**details, 'Task finished on': finished_on.isoformat()}

    return response_api_success(data={
        'row': projected,
        'details': details,
    })
