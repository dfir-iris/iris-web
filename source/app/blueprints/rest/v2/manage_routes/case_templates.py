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


# ----- Schema introspection -------------------------------------------
#
# Powers the interactive editor on the Settings Case Templates page.
# The frontend needs to know, per field: type, required, optional
# length cap, free-form help. Rather than duplicating that metadata
# client-side we introspect `CaseTemplateSchema` at request time so a
# field added to the Marshmallow schema shows up in the UI without
# any frontend change.
#
# The nested template shapes for tasks + note directories + notes are
# NOT real Marshmallow schemas — `validate_case_template` enforces
# them with hand-rolled checks on raw dicts. We mirror those rules
# here as static descriptors so the frontend renders the same fields
# the validator accepts. When the validator gains a new field this
# descriptor must be updated to match.

import marshmallow.fields as mf
import marshmallow.validate as mv


def _describe_marshmallow_field(field) -> Dict[str, Any]:
    """Best-effort projection of a Marshmallow field to a UI descriptor.

    Picks a coarse `kind` the frontend can switch on (`string`,
    `text`, `integer`, `list[string]`, `list[object]`) and surfaces
    `required`, `allow_none`, `missing` plus any `Length` validator's
    max constraint — those are the four hints the form widgets need.

    Everything more specific (e.g. enum membership) is left to the
    schema's own `verify_*` hooks at save time; we don't try to
    enumerate every Marshmallow validator type.
    """
    # The plain `String` field is the catch-all; we treat long-form
    # description / summary as `text` (multi-line) by name convention
    # since Marshmallow doesn't model that distinction.
    if isinstance(field, mf.Integer):
        kind = 'integer'
    elif isinstance(field, mf.List):
        # Inspect the inner type to disambiguate string lists (tags)
        # from object lists (note_directories with their `notes`
        # children). Anything else falls back to 'list[object]'.
        inner = field.inner
        if isinstance(inner, mf.String):
            kind = 'list[string]'
        elif isinstance(inner, mf.Dict):
            kind = 'list[object]'
        else:
            kind = 'list[object]'
    elif isinstance(field, mf.Boolean):
        kind = 'boolean'
    elif isinstance(field, mf.DateTime):
        kind = 'datetime'
    else:
        kind = 'string'

    max_length = None
    for validator in field.validators or ():
        if isinstance(validator, mv.Length) and validator.max is not None:
            max_length = validator.max
            break

    return {
        'kind': kind,
        'required': bool(field.required),
        'allow_none': bool(field.allow_none),
        'dump_only': bool(field.dump_only),
        'max_length': max_length,
    }


# Nested template shapes — these match the rules enforced by
# `validate_case_template` in datamgmt/manage/manage_case_templates_db.py.
_TASK_TEMPLATE_FIELDS = [
    {
        'name': 'title',
        'label': 'Title',
        'kind': 'string',
        'required': True,
        'help': 'Becomes the new task title.',
    },
    {
        'name': 'description',
        'label': 'Description',
        'kind': 'text',
        'required': False,
        'help': 'Optional. Appears in the task detail panel.',
    },
    {
        'name': 'tags',
        'label': 'Tags',
        'kind': 'list[string]',
        'required': False,
        'help': 'Optional. Comma-separated when applied.',
    },
]

_NOTE_TEMPLATE_FIELDS = [
    {
        'name': 'title',
        'label': 'Title',
        'kind': 'string',
        'required': True,
    },
    {
        'name': 'content',
        'label': 'Content',
        'kind': 'text',
        'required': False,
        'help': 'Markdown is supported.',
    },
]

_NOTE_DIRECTORY_TEMPLATE_FIELDS = [
    {
        'name': 'title',
        'label': 'Directory name',
        'kind': 'string',
        'required': True,
    },
    {
        'name': 'notes',
        'label': 'Notes',
        'kind': 'list[object]',
        'required': False,
        'item_schema': 'note',
    },
]

# Friendly labels + per-field help text. Keyed by the schema's
# field name so a future rename on the schema only needs to update
# the schema; this dict can stay or be edited deliberately.
_FIELD_LABELS: Dict[str, Dict[str, str]] = {
    'name': {
        'label': 'Name',
        'help': "Short, unique slug. Required.",
    },
    'display_name': {
        'label': 'Display name',
        'help': "Shown in the picker; falls back to `name`.",
    },
    'description': {
        'label': 'Description',
        'help': "Admin-side description, not visible on cases.",
    },
    'author': {'label': 'Author', 'help': 'Optional. Up to 128 characters.'},
    'title_prefix': {
        'label': 'Case title prefix',
        'help': 'Prepended to the case name on apply. Up to 32 characters.',
    },
    'summary': {
        'label': 'Summary',
        'help': 'Appended to the case description on apply.',
    },
    'tags': {'label': 'Tags', 'help': 'Appended to the case tags on apply.'},
    'classification': {
        'label': 'Classification',
        'help': "Must match the `name` of an existing case classification.",
    },
    'note_directories': {
        'label': 'Note directories',
        'help': 'Created on the case on apply.',
    },
    'tasks': {
        'label': 'Tasks',
        'help': 'Created on the case on apply, with status "To Do".',
    },
}

# Field-name overrides where the introspected `kind` is wrong for the
# UI (Marshmallow has no `text` field, but `description` / `summary`
# render better as textareas). Keyed by schema field name.
_KIND_OVERRIDES: Dict[str, str] = {
    'description': 'text',
    'summary': 'text',
}

# Which item descriptor a `list[object]` field renders inside the
# repeater. Keyed by schema field name; missing entries fall back to
# a generic "object" with no fields, which the UI renders as a
# read-only JSON snippet so the form stays useful for unknown shapes.
_ITEM_SCHEMA_BY_FIELD: Dict[str, str] = {
    'tasks': 'task',
    'note_directories': 'note_directory',
}


@case_templates_blueprint.get('/schema')
@ac_api_requires(Permissions.case_templates_read)
def get_case_template_schema() -> Response:
    """Describe `CaseTemplateSchema` + nested template shapes.

    Returned shape is consumed by the interactive editor to build the
    form. Keeping introspection here (rather than client-side) keeps
    the form in lockstep with the backend schema — adding a field to
    `CaseTemplateSchema` adds an input on the form on the next reload.

    `tasks` is special-cased: it's stored as raw JSON on the model
    and never declared as a Marshmallow field, but the post-modifier
    treats it as a structured list. We expose it as if it were a
    declared field so the UI can build the same repeater the rest of
    the form uses.
    """
    schema = CaseTemplateSchema()
    fields_out: List[Dict[str, Any]] = []

    # CaseTemplateSchema.fields is an OrderedDict; preserves
    # declaration order, which is the order users see in the form.
    for name, field in schema.fields.items():
        descriptor = _describe_marshmallow_field(field)
        meta = _FIELD_LABELS.get(name, {})
        kind = _KIND_OVERRIDES.get(name, descriptor['kind'])
        entry: Dict[str, Any] = {
            'name': name,
            'label': meta.get('label', name.replace('_', ' ').capitalize()),
            'help': meta.get('help', ''),
            **descriptor,
            'kind': kind,
        }
        item_schema = _ITEM_SCHEMA_BY_FIELD.get(name)
        if item_schema is not None:
            entry['item_schema'] = item_schema
        fields_out.append(entry)

    return response_api_success({
        'fields': fields_out,
        'item_schemas': {
            'task': _TASK_TEMPLATE_FIELDS,
            'note_directory': _NOTE_DIRECTORY_TEMPLATE_FIELDS,
            'note': _NOTE_TEMPLATE_FIELDS,
        },
    })


