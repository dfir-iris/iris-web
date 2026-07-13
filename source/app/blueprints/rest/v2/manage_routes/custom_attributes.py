"""v2 admin endpoints for the CustomAttribute taxonomy.

Each row of `custom_attribute` describes the *schema* attached to one
object type — case, IOC, asset, task, note, evidence, event, client.
`attribute_content` is a JSON document:

    {
        "<Tab name>": {
            "<Field name>": {
                "type": "input_string"|"input_textfield"|"input_checkbox"
                        |"input_select"|"input_date"|"input_datetime"
                        |"raw"|"html",
                "value": <default value>,
                "mandatory": <bool>,
                "options": ["only", "for", "input_select"]
            }
        }
    }

The SPA admin page reads the row, lets the user edit the JSON in a
form (the legacy interface had a freeform JSON editor — we mirror
that), then PATCHes it back. The backend re-runs
`validate_attribute(...)` (same helper the legacy route used) so the
schema can't drift into an unsupported shape and `update_all_attributes`
back-fills the existing object rows with the new tabs / fields so the
detail pages render the new entries on the next load.
"""
from __future__ import annotations

import json
from typing import Any
from typing import Dict
from typing import List

from flask import Blueprint
from flask import Response
from flask import request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.datamgmt.manage.manage_attribute_db import update_all_attributes
from app.datamgmt.manage.manage_attribute_db import validate_attribute
from app.db import db
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.models.models import CustomAttribute


# Object types the legacy code knew about. Mirrors the `attribute_for`
# values stored on existing rows.
_ALLOWED_OBJECT_TYPES = {
    'case',
    'ioc',
    'asset',
    'task',
    'note',
    'evidence',
    'event',
    'client',
}


def _serialize(row: CustomAttribute) -> Dict[str, Any]:
    return {
        'attribute_id': row.attribute_id,
        'attribute_display_name': row.attribute_display_name,
        'attribute_description': row.attribute_description,
        'attribute_for': row.attribute_for,
        'attribute_content': row.attribute_content or {},
    }


custom_attributes_blueprint = Blueprint(
    'custom_attributes_rest_v2', __name__, url_prefix='/custom-attributes'
)


@custom_attributes_blueprint.get('')
@ac_api_requires()
def list_custom_attributes() -> Response:
    """List every attribute-definition row.

    Readable by any authenticated user because the schema is
    needed to render the detail-view tabs (not just by admins). Write
    access is still admin-only via PUT below.
    """
    object_type = (request.args.get('attribute_for') or '').strip().lower() or None
    if object_type and object_type not in _ALLOWED_OBJECT_TYPES:
        return response_api_error(
            f"Unknown attribute_for filter: {object_type}"
        )

    query = CustomAttribute.query
    if object_type is not None:
        query = query.filter(CustomAttribute.attribute_for == object_type)

    rows = query.order_by(CustomAttribute.attribute_for.asc()).all()
    return response_api_success([_serialize(r) for r in rows])


@custom_attributes_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_custom_attribute(identifier: int) -> Response:
    row = CustomAttribute.query.filter(CustomAttribute.attribute_id == identifier).first()
    if row is None:
        return response_api_not_found()
    return response_api_success(_serialize(row))


@custom_attributes_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def update_custom_attribute(identifier: int) -> Response:
    """Update one attribute-definition row.

    Body shape:

        {
            "attribute_content": "<JSON-stringified schema>" | {schema},
            "complete_overwrite": <bool>,   # optional
            "partial_overwrite": <bool>     # optional
        }

    `attribute_content` is accepted as either a raw object or a
    JSON-encoded string — the legacy admin page sent it stringified;
    the new SPA panel will send the object directly. Both paths feed
    into `validate_attribute` which expects a string, so we re-encode
    when needed.

    `complete_overwrite` / `partial_overwrite` propagate into
    `update_all_attributes` so the change is back-filled across every
    existing record of the matching object type.
    """
    row = CustomAttribute.query.filter(CustomAttribute.attribute_id == identifier).first()
    if row is None:
        return response_api_not_found()

    if not request.is_json:
        return response_api_error('Invalid request')

    body = request.get_json() or {}
    raw_content = body.get('attribute_content')
    if raw_content is None:
        return response_api_error('Missing attribute_content')

    if isinstance(raw_content, (dict, list)):
        encoded = json.dumps(raw_content)
    elif isinstance(raw_content, str):
        encoded = raw_content
    else:
        return response_api_error('attribute_content must be a string or JSON object')

    parsed, logs = validate_attribute(encoded)
    if logs:
        return response_api_error('Invalid attribute schema', data=logs)

    previous = row.attribute_content
    row.attribute_content = parsed

    if 'attribute_display_name' in body and isinstance(body['attribute_display_name'], str):
        row.attribute_display_name = body['attribute_display_name'].strip() or row.attribute_display_name
    if 'attribute_description' in body and isinstance(body['attribute_description'], str):
        row.attribute_description = body['attribute_description'].strip() or row.attribute_description

    db.session.commit()

    complete_overwrite = bool(body.get('complete_overwrite'))
    partial_overwrite = bool(body.get('partial_overwrite'))
    update_all_attributes(
        row.attribute_for,
        partial_overwrite=partial_overwrite,
        complete_overwrite=complete_overwrite,
        previous_attribute=previous,
    )

    track_activity(
        f'Updated custom attribute schema "{row.attribute_display_name}" ({row.attribute_for})',
        ctx_less=True,
    )

    return response_api_success(_serialize(row))


@custom_attributes_blueprint.post('/validate')
@ac_api_requires(Permissions.server_administrator)
def validate_custom_attribute() -> Response:
    """Dry-run the schema validator without mutating anything.

    The SPA calls this from the edit modal so admins can see the
    exact per-field error list before committing (the PUT would run
    `update_all_attributes` and back-fill every existing row, which
    is expensive — surfacing validation errors early avoids paying
    that cost only to be rejected).

    Body: `{"attribute_content": <object | JSON string>}`.
    Returns `{ok: bool, logs: [...]}` — `logs` is empty on success.
    """
    if not request.is_json:
        return response_api_error('Invalid request')

    body = request.get_json() or {}
    raw_content = body.get('attribute_content')
    if raw_content is None:
        return response_api_error('Missing attribute_content')

    if isinstance(raw_content, (dict, list)):
        encoded = json.dumps(raw_content)
    elif isinstance(raw_content, str):
        encoded = raw_content
    else:
        return response_api_error('attribute_content must be a string or JSON object')

    _parsed, logs = validate_attribute(encoded)
    return response_api_success({'ok': not logs, 'logs': logs})
