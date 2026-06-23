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

from sqlalchemy import desc
from sqlalchemy import or_

from app.models.models import CeleryTaskMeta


def search_asynchronous_tasks(count):
    tasks = CeleryTaskMeta.query.filter(
        ~ CeleryTaskMeta.name.like('app.iris_engine.updater.updater.%')
    ).order_by(desc(CeleryTaskMeta.date_done)).limit(count).all()
    return tasks


def search_asynchronous_tasks_paginated(
        page=1,
        per_page=25,
        search_value=None,
        status=None,
):
    """Paginated listing of CeleryTaskMeta rows for the Dim Tasks page.

    Same row source as ``search_asynchronous_tasks`` but with proper
    pagination + optional filters. We filter out updater tasks (same as
    the legacy listing) and offer a coarse ``search`` over the task name
    plus a ``status`` exact-match filter.

    ``args`` / ``kwargs`` / ``result`` are LargeBinary (pickled) columns
    — we deliberately do NOT filter on them, because that would either
    require unpickling every row (security + performance hazard) or
    binary-substring ILIKE'ing pickled bytes (false positives). The
    business layer does the pickle decoding lazily on the items the page
    returns.
    """
    base = CeleryTaskMeta.query.filter(
        ~ CeleryTaskMeta.name.like('app.iris_engine.updater.updater.%')
    )

    if search_value:
        like = f'%{search_value}%'
        base = base.filter(or_(
            CeleryTaskMeta.name.ilike(like),
            CeleryTaskMeta.task_id.ilike(like),
        ))

    if status:
        base = base.filter(CeleryTaskMeta.status == status)

    return base.order_by(desc(CeleryTaskMeta.date_done)).paginate(
        page=page, per_page=per_page, error_out=False,
    )


def get_asynchronous_task_by_id(task_id):
    """Single CeleryTaskMeta row by Celery task id, or None."""
    return CeleryTaskMeta.query.filter(CeleryTaskMeta.task_id == task_id).first()
