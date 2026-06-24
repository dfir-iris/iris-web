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

"""v2 endpoints for the Case Templates admin family.

Differences from the legacy `/manage/case-templates/...` surface:

* Bodies are plain JSON — no more `{case_template_json: "stringified"}`
  envelope. The legacy form was a workaround for upload modals that
  posted file contents as a single string field; the v2 page reads
  the file client-side and POSTs the parsed object directly.
* List supports pagination + ILIKE substring search via `search`.
"""

from typing import Any
from typing import Dict
from typing import Optional

from flask import Blueprint
from flask import Response
from flask import request
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.datamgmt.filtering import paginate
from app.datamgmt.manage.manage_case_templates_db import delete_case_template_by_id
from app.datamgmt.manage.manage_case_templates_db import get_case_template_by_id
from app.datamgmt.manage.manage_case_templates_db import validate_case_template
from app.db import db
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.models.models import CaseTemplate
from app.schema.marshables import CaseTemplateSchema


case_templates_blueprint = Blueprint('case_templates_rest_v2', __name__, url_prefix='/case-templates')


_SEARCH_COLUMNS = ('name', 'display_name', 'description', 'author', 'title_prefix')


def _to_dict(payload: Any) -> Dict[str, Any]:
    """Tolerate both v2-native (object) and legacy (`case_template_json`) bodies.

    The legacy IRIS upload modal POSTed the raw file contents as a
    string field — keep accepting that so an admin who has an old
    template JSON file can paste it via the upload flow without
    having to wrap it. The page itself sends a plain object.
    """
    if isinstance(payload, dict) and 'case_template_json' in payload and isinstance(
        payload['case_template_json'], str
    ):
        import json as _json
        try:
            parsed = _json.loads(payload['case_template_json'])
        except Exception as exc:
            raise ValueError(f'Invalid JSON in case_template_json: {exc}')
        return parsed if isinstance(parsed, dict) else {}
    return payload if isinstance(payload, dict) else {}


def _persist_from_dict(template_dict: Dict[str, Any], *, update_target: Optional[CaseTemplate] = None) -> CaseTemplate:
    """Shared validate + load + commit step for create + update.

    Returns the persisted (or refreshed) `CaseTemplate` row. Raises
    `ValueError` with a user-facing message on validation failure so
    the route layer can surface it cleanly.
    """
    is_update = update_target is not None
    error = validate_case_template(template_dict, update=is_update)
    if error is not None:
        raise ValueError(error)

    schema = CaseTemplateSchema()
    try:
        if is_update:
            data = schema.load(template_dict, partial=True)
            update_target.update_from_dict(data)
            db.session.commit()
            return update_target
        template_dict.setdefault('created_by_user_id', iris_current_user.id)
        data = schema.load(template_dict)
        row = CaseTemplate(**data)
        db.session.add(row)
        db.session.commit()
        return row
    except ValidationError as exc:
        db.session.rollback()
        raise ValueError(str(exc.messages))
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError(f'Database error: {exc}')


def _list_query():
    """SQLAlchemy query feeding the paginated list.

    We `paginate(model=CaseTemplate, ...)` so the existing pagination
    helper can apply `order_by` + `sort_dir` against any column on
    the model — same shape as every other v2 list endpoint.
    """
    query = CaseTemplate.query
    search = (request.args.get('search') or '').strip() or None
    if search:
        from sqlalchemy import or_
        needle = f'%{search}%'
        clauses = []
        for column_name in _SEARCH_COLUMNS:
            column = getattr(CaseTemplate, column_name, None)
            if column is not None:
                clauses.append(column.ilike(needle))
        if clauses:
            query = query.filter(or_(*clauses))
    return query


# ----- Routes ----------------------------------------------------------

@case_templates_blueprint.get('')
@ac_api_requires(Permissions.case_templates_read)
def list_case_templates() -> Response:
    pagination_parameters = parse_pagination_parameters(request)
    paginated = paginate(CaseTemplate, pagination_parameters, _list_query())
    return response_api_paginated(CaseTemplateSchema(), paginated)


@case_templates_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.case_templates_read)
def get_case_template(identifier: int) -> Response:
    row = get_case_template_by_id(identifier)
    if row is None:
        return response_api_not_found()
    return response_api_success(CaseTemplateSchema().dump(row))


@case_templates_blueprint.post('')
@ac_api_requires(Permissions.case_templates_write)
def create_case_template() -> Response:
    try:
        template_dict = _to_dict(request.get_json() or {})
    except ValueError as exc:
        return response_api_error(str(exc))

    if not template_dict:
        return response_api_error('Missing template body')

    try:
        row = _persist_from_dict(template_dict)
    except ValueError as exc:
        return response_api_error('Invalid case template', data=str(exc))

    track_activity(f"Case template '{row.name}' added", ctx_less=True)
    return response_api_created(CaseTemplateSchema().dump(row))


@case_templates_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.case_templates_write)
def update_case_template(identifier: int) -> Response:
    row = get_case_template_by_id(identifier)
    if row is None:
        return response_api_not_found()

    try:
        template_dict = _to_dict(request.get_json() or {})
    except ValueError as exc:
        return response_api_error(str(exc))

    if not template_dict:
        return response_api_error('Missing template body')

    try:
        row = _persist_from_dict(template_dict, update_target=row)
    except ValueError as exc:
        return response_api_error('Invalid case template', data=str(exc))

    track_activity(f"Case template '{row.name}' updated", ctx_less=True)
    return response_api_success(CaseTemplateSchema().dump(row))


@case_templates_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.case_templates_write)
def delete_case_template(identifier: int) -> Response:
    row = get_case_template_by_id(identifier)
    if row is None:
        return response_api_not_found()
    name = row.name
    delete_case_template_by_id(identifier)
    db.session.commit()
    track_activity(f"Case template '{name}' deleted", ctx_less=True)
    return response_api_deleted()


