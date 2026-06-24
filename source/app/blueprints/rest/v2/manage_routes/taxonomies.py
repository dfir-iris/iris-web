#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
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

"""v2 read-only taxonomy endpoints.

The seven taxonomies here are seed data: small tables (typically
<20 rows) populated at install time, occasionally extended via SQL
or by admin scripts. The UI only needs to *read* them — case/IOC/
asset/alert modals look up the rows to populate dropdowns.

A single file with one blueprint per resource (mounted under
`/api/v2/manage/<resource>`) keeps these next to the heavier
`case_objects.py` taxonomies for discoverability. Each blueprint
exposes only `GET /` with optional pagination + ILIKE `search` — no
write methods. Adding write methods later only needs the existing
`Permissions.server_administrator` decorator and a Marshmallow
`load_instance=True` schema.
"""

from typing import Any
from typing import Iterable
from typing import Type

from flask import Blueprint
from flask import Response
from flask import request
from sqlalchemy import or_

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_success
from app.datamgmt.filtering import paginate
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.models.alerts import AlertResolutionStatus
from app.models.alerts import AlertStatus
from app.models.alerts import Severity
from app.models.assets import AnalysisStatus
from app.models.authorization import Permissions
from app.models.iocs import Tlp
from app.models.models import EventCategory
from app.models.models import TaskStatus
from app.schema.marshables import AlertResolutionSchema
from app.schema.marshables import AlertStatusSchema
from app.schema.marshables import AnalysisStatusSchema
from app.schema.marshables import EventCategorySchema
from app.schema.marshables import SeveritySchema
from app.schema.marshables import TaskStatusSchema
from app.schema.marshables import TlpSchema


def _list_endpoint(
    model: Type[Any],
    schema_factory,
    search_columns: Iterable[str],
    order_column: str,
):
    """Build a `GET /` handler for a single taxonomy.

    Returns a paginated envelope so the frontend's generic
    list-state plumbing works out of the box. `search` is an ILIKE
    against the columns listed; `order_column` is the deterministic
    sort applied before paginating.
    """
    def handler() -> Response:
        pagination_parameters = parse_pagination_parameters(request)
        query = model.query
        search = (request.args.get('search') or '').strip() or None
        if search:
            needle = f'%{search}%'
            clauses = []
            for column_name in search_columns:
                column = getattr(model, column_name, None)
                if column is not None:
                    clauses.append(column.ilike(needle))
            if clauses:
                query = query.filter(or_(*clauses))
        order_column_obj = getattr(model, order_column, None)
        if order_column_obj is not None:
            query = query.order_by(order_column_obj.asc())
        paginated = paginate(model, pagination_parameters, query)
        return response_api_success({
            'total': paginated.total,
            'data': schema_factory().dump(paginated.items, many=True),
            'last_page': paginated.pages,
            'current_page': paginated.page,
            'next_page': paginated.next_num if paginated.has_next else None,
        })

    return handler


def _build_readonly_blueprint(
    url_prefix: str,
    blueprint_name: str,
    model: Type[Any],
    schema_factory,
    search_columns: Iterable[str],
    order_column: str,
) -> Blueprint:
    bp = Blueprint(blueprint_name, __name__, url_prefix=f'/{url_prefix}')

    @bp.get('')
    @ac_api_requires()
    def list_route() -> Response:
        return _list_endpoint(model, schema_factory, search_columns, order_column)()

    return bp


# Each taxonomy gets its own blueprint so URLs stay readable in logs
# and existing-prefix-based proxy rules can target them individually.
severities_blueprint = _build_readonly_blueprint(
    url_prefix='severities',
    blueprint_name='severities_rest_v2',
    model=Severity,
    schema_factory=SeveritySchema,
    search_columns=('severity_name', 'severity_description'),
    order_column='severity_id',
)

tlp_blueprint = _build_readonly_blueprint(
    url_prefix='tlp',
    blueprint_name='tlp_rest_v2',
    model=Tlp,
    schema_factory=TlpSchema,
    search_columns=('tlp_name',),
    order_column='tlp_id',
)

alert_statuses_blueprint = _build_readonly_blueprint(
    url_prefix='alert-statuses',
    blueprint_name='alert_statuses_rest_v2',
    model=AlertStatus,
    schema_factory=AlertStatusSchema,
    search_columns=('status_name', 'status_description'),
    order_column='status_id',
)

alert_resolutions_blueprint = _build_readonly_blueprint(
    url_prefix='alert-resolutions',
    blueprint_name='alert_resolutions_rest_v2',
    model=AlertResolutionStatus,
    schema_factory=AlertResolutionSchema,
    search_columns=('resolution_status_name', 'resolution_status_description'),
    order_column='resolution_status_id',
)

analysis_statuses_blueprint = _build_readonly_blueprint(
    url_prefix='analysis-statuses',
    blueprint_name='analysis_statuses_rest_v2',
    model=AnalysisStatus,
    schema_factory=AnalysisStatusSchema,
    search_columns=('name',),
    order_column='id',
)

event_categories_blueprint = _build_readonly_blueprint(
    url_prefix='event-categories',
    blueprint_name='event_categories_rest_v2',
    model=EventCategory,
    schema_factory=EventCategorySchema,
    search_columns=('name',),
    order_column='id',
)

task_statuses_blueprint = _build_readonly_blueprint(
    url_prefix='task-statuses',
    blueprint_name='task_statuses_rest_v2',
    model=TaskStatus,
    schema_factory=TaskStatusSchema,
    search_columns=('status_name', 'status_description'),
    order_column='id',
)


# A single parent blueprint groups them under /api/v2/manage so the
# `manage.py` registration line stays a single import per family.
taxonomies_blueprint = Blueprint('taxonomies_rest_v2', __name__)

taxonomies_blueprint.register_blueprint(severities_blueprint)
taxonomies_blueprint.register_blueprint(tlp_blueprint)
taxonomies_blueprint.register_blueprint(alert_statuses_blueprint)
taxonomies_blueprint.register_blueprint(alert_resolutions_blueprint)
taxonomies_blueprint.register_blueprint(analysis_statuses_blueprint)
taxonomies_blueprint.register_blueprint(event_categories_blueprint)
taxonomies_blueprint.register_blueprint(task_statuses_blueprint)
