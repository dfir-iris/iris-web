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

"""v2 endpoints for the Report Templates admin family.

Differences from the legacy `/manage/templates/...` surface:

* Bodies for metadata-only updates are plain JSON instead of
  multipart — uploads stay multipart, but renames / description
  edits / language swap don't need to re-upload the file.
* Read endpoints paginate + accept a `search` query parameter.
* `POST /<id>/render` triggers the existing
  `generate_investigation_report` / `generate_activities_report`
  flow and streams the resulting file back inline. The current user
  must hold `read_only`-or-better on the target case — same gate
  every case-scoped v2 endpoint uses.
* `GET /accessible-cases` powers the case picker in the editor, also
  scoped to cases the caller can access.
* `GET /schema` ships the model field metadata + the seeded
  `languages` / `report_types` rows so the form can render selects
  without extra round-trips.
"""

import os
import random
import string
import tempfile
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from flask import Blueprint
from flask import Response
from flask import request
from flask import send_file
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from app import app
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.business.reports.reports import generate_activities_report
from app.business.reports.reports import generate_investigation_report
from app.datamgmt.filtering import paginate
from app.db import db
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.models.authorization import Permissions
from app.models.authorization import User
from app.models.cases import Cases
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.models import CaseTemplateReport
from app.models.models import Languages
from app.models.models import ReportType
from app.util import FileRemover


report_templates_blueprint = Blueprint(
    'report_templates_rest_v2', __name__, url_prefix='/report-templates'
)


# Same extension allowlist as the legacy upload — DocxGenerator handles
# .doc/.docx, the Jinja+text pipeline handles .md/.html. Anything else
# would just blow up in the renderer with a less helpful error.
_ALLOWED_EXTENSIONS = {'md', 'html', 'doc', 'docx'}

# Same file remover used by the legacy report routes — cleans up the
# rendered file from /tmp once the response has streamed.
_FILE_REMOVER = FileRemover()


def _allowed_filename(filename: str) -> bool:
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in _ALLOWED_EXTENSIONS
    )


def _random_filename(extension: str) -> str:
    letters = string.ascii_lowercase
    stem = ''.join(random.choice(letters) for _ in range(18))
    return f'{stem}{extension}'


def _serialize_template(template: CaseTemplateReport) -> Dict[str, Any]:
    """Single source of truth for the template's JSON projection.

    Used by every list / read / update / render-success response so
    the frontend sees one shape everywhere. Includes the joined
    `created_by` user name and `language` / `report_type` names since
    the picker UI uses them as readable labels.
    """
    return {
        'id': template.id,
        'name': template.name,
        'description': template.description,
        'naming_format': template.naming_format,
        'internal_reference': template.internal_reference,
        'date_created': template.date_created.isoformat() if template.date_created else None,
        'created_by_user_id': template.created_by_user_id,
        'created_by': template.created_by_user.name if template.created_by_user else None,
        'language_id': template.language_id,
        'language_code': template.language.code if template.language else None,
        'language_name': template.language.name if template.language else None,
        'report_type_id': template.report_type_id,
        'report_type_name': template.report_type.name if template.report_type else None,
    }


def _get_template(identifier: int) -> CaseTemplateReport:
    row = CaseTemplateReport.query.filter(CaseTemplateReport.id == identifier).first()
    if row is None:
        raise ObjectNotFoundError()
    return row


def _list_query():
    query = CaseTemplateReport.query
    search = (request.args.get('search') or '').strip() or None
    if search:
        from sqlalchemy import or_
        needle = f'%{search}%'
        query = query.filter(
            or_(
                CaseTemplateReport.name.ilike(needle),
                CaseTemplateReport.description.ilike(needle),
                CaseTemplateReport.naming_format.ilike(needle),
            )
        )
    return query


# ----- CRUD -----------------------------------------------------------

@report_templates_blueprint.get('')
@ac_api_requires(Permissions.server_administrator)
def list_report_templates() -> Response:
    pagination_parameters = parse_pagination_parameters(request)
    paginated = paginate(CaseTemplateReport, pagination_parameters, _list_query())
    # `response_api_paginated` takes a Marshmallow schema; we don't
    # have one for this model, so synthesise the envelope directly.
    items = [_serialize_template(t) for t in paginated.items]
    return response_api_success({
        'total': paginated.total,
        'data': items,
        'last_page': paginated.pages,
        'current_page': paginated.page,
        'next_page': paginated.next_num if paginated.has_next else None,
    })


@report_templates_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def get_report_template(identifier: int) -> Response:
    try:
        return response_api_success(_serialize_template(_get_template(identifier)))
    except ObjectNotFoundError:
        return response_api_not_found()


@report_templates_blueprint.post('')
@ac_api_requires(Permissions.server_administrator)
def create_report_template() -> Response:
    """Multipart upload: metadata in form fields + the template file
    under the `file` key. Mirrors the legacy endpoint so existing
    template files round-trip without modification.
    """
    upload = request.files.get('file')
    if upload is None or not upload.filename:
        return response_api_error('No file uploaded')

    if not _allowed_filename(upload.filename):
        return response_api_error(
            f"File extension not allowed. Use one of: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
        )

    name = (request.form.get('name') or '').strip()
    if not name:
        return response_api_error('Field `name` is required')

    description = (request.form.get('description') or '').strip()
    naming_format = (request.form.get('naming_format') or '').strip()
    language_id = request.form.get('language_id', type=int)
    report_type_id = request.form.get('report_type_id', type=int)

    if language_id is None or report_type_id is None:
        return response_api_error('`language_id` and `report_type_id` are required')

    if Languages.query.filter(Languages.id == language_id).first() is None:
        return response_api_error('Unknown language_id')
    if ReportType.query.filter(ReportType.id == report_type_id).first() is None:
        return response_api_error('Unknown report_type_id')

    safe_name = secure_filename(upload.filename)
    _, extension = os.path.splitext(safe_name)
    stored_filename = _random_filename(extension)

    try:
        upload.save(os.path.join(app.config['TEMPLATES_PATH'], stored_filename))
    except Exception as exc:
        return response_api_error(f'Unable to save uploaded file: {exc}')

    template = CaseTemplateReport(
        name=name,
        description=description,
        naming_format=naming_format,
        internal_reference=stored_filename,
        language_id=language_id,
        report_type_id=report_type_id,
        created_by_user_id=iris_current_user.id,
        date_created=datetime.utcnow(),
    )
    try:
        db.session.add(template)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        # Best-effort cleanup so we don't orphan the just-uploaded
        # file when the metadata insert fails. The fs delete is
        # secondary — if it fails the orphan stays but the API still
        # surfaces the original IntegrityError.
        try:
            os.unlink(os.path.join(app.config['TEMPLATES_PATH'], stored_filename))
        except Exception:
            pass
        return response_api_error(f'Database error: {exc}')

    track_activity(f"Report template '{template.name}' added", ctx_less=True)
    return response_api_created(_serialize_template(template))


@report_templates_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def update_report_template(identifier: int) -> Response:
    """Metadata-only update. Takes JSON so admins can rename / re-tag
    a template without re-uploading its file. To replace the file
    itself, use `PUT /<id>/file` (multipart) — kept separate so this
    route can stay plain JSON.
    """
    try:
        template = _get_template(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()

    body = request.get_json() or {}
    if not isinstance(body, dict):
        return response_api_error('Body must be a JSON object')

    if 'name' in body:
        name = (body.get('name') or '').strip()
        if not name:
            return response_api_error('`name` cannot be empty')
        template.name = name

    for plain_field in ('description', 'naming_format'):
        if plain_field in body:
            template.__setattr__(plain_field, (body.get(plain_field) or '').strip())

    if 'language_id' in body:
        lang_id = body['language_id']
        if not isinstance(lang_id, int) or Languages.query.filter(Languages.id == lang_id).first() is None:
            return response_api_error('Unknown language_id')
        template.language_id = lang_id

    if 'report_type_id' in body:
        rt_id = body['report_type_id']
        if not isinstance(rt_id, int) or ReportType.query.filter(ReportType.id == rt_id).first() is None:
            return response_api_error('Unknown report_type_id')
        template.report_type_id = rt_id

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        return response_api_error(f'Database error: {exc}')

    track_activity(f"Report template '{template.name}' updated", ctx_less=True)
    return response_api_success(_serialize_template(template))


@report_templates_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def delete_report_template(identifier: int) -> Response:
    """Delete metadata + the underlying file. Best-effort file
    unlink: if it fails (already removed manually, FS permissions
    drift) the row still goes — the legacy endpoint did the same.
    """
    try:
        template = _get_template(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()

    name = template.name
    fs_error: Optional[str] = None
    try:
        os.unlink(os.path.join(app.config['TEMPLATES_PATH'], template.internal_reference))
    except FileNotFoundError:
        pass
    except Exception as exc:
        fs_error = str(exc)

    CaseTemplateReport.query.filter(CaseTemplateReport.id == identifier).delete()
    db.session.commit()

    track_activity(f"Report template '{name}' deleted", ctx_less=True)

    if fs_error:
        return response_api_success({
            'warning': f'Template row deleted but the file could not be removed: {fs_error}'
        })
    return response_api_deleted()


# ----- File replacement ----------------------------------------------

@report_templates_blueprint.put('/<int:identifier>/file')
@ac_api_requires(Permissions.server_administrator)
def replace_report_template_file(identifier: int) -> Response:
    """Replace the underlying template file in place.

    Multipart: a single `file` field, same allowlist as the create
    endpoint. The renderer reads the file from disk every time a
    report is generated, so an in-place swap is safe between
    requests — no caching to invalidate.

    Strategy: write the new file under a fresh random name first,
    then atomically flip `internal_reference` to point at it and
    unlink the old file. If the upload or DB update fails we drop
    the staged file, leaving the original intact.
    """
    try:
        template = _get_template(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()

    upload = request.files.get('file')
    if upload is None or not upload.filename:
        return response_api_error('No file uploaded')

    if not _allowed_filename(upload.filename):
        return response_api_error(
            f"File extension not allowed. Use one of: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
        )

    safe_name = secure_filename(upload.filename)
    _, extension = os.path.splitext(safe_name)
    new_filename = _random_filename(extension)
    new_path = os.path.join(app.config['TEMPLATES_PATH'], new_filename)

    try:
        upload.save(new_path)
    except Exception as exc:
        return response_api_error(f'Unable to save uploaded file: {exc}')

    old_filename = template.internal_reference
    template.internal_reference = new_filename
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        # DB write lost — discard the just-uploaded file so we don't
        # orphan it on disk. The old file is still pointed at by the
        # template row, so the render flow remains usable.
        try:
            os.unlink(new_path)
        except Exception:
            pass
        return response_api_error(f'Database error: {exc}')

    # Best-effort cleanup of the previous file. If this fails the
    # only downside is an orphan on disk — the row already points at
    # the new file, so users see the update. Don't fail the request.
    try:
        os.unlink(os.path.join(app.config['TEMPLATES_PATH'], old_filename))
    except FileNotFoundError:
        pass
    except Exception:
        # Log via track_activity so the orphan is traceable.
        track_activity(
            f"Report template '{template.name}' file replaced; "
            f"could not remove previous file '{old_filename}'",
            ctx_less=True,
        )
    else:
        track_activity(
            f"Report template '{template.name}' file replaced",
            ctx_less=True,
        )

    return response_api_success(_serialize_template(template))


# ----- File download --------------------------------------------------

@report_templates_blueprint.get('/<int:identifier>/download')
@ac_api_requires(Permissions.server_administrator)
def download_report_template(identifier: int) -> Response:
    """Stream the raw template file back so an admin can inspect /
    edit / copy it locally. Filename uses the human-readable
    `template.name` with the stored extension."""
    try:
        template = _get_template(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()

    fpath = os.path.join(app.config['TEMPLATES_PATH'], template.internal_reference)
    if not os.path.exists(fpath):
        return response_api_error('Template file is missing on disk')

    _, extension = os.path.splitext(template.internal_reference)
    # Drop the leading dot and any path separators a malicious name
    # could carry over from earlier renames.
    safe_display = secure_filename(template.name) or 'report_template'
    return send_file(fpath, as_attachment=True, download_name=f'{safe_display}{extension}')


# ----- Render against a case -----------------------------------------

@report_templates_blueprint.post('/<int:identifier>/render')
@ac_api_requires(Permissions.server_administrator)
def render_report_template(identifier: int) -> Response:
    """Render the template against a real case and stream the result.

    Body: `{case_id: int, safe_mode?: bool}`. The current user must
    hold `read_only`-or-better on the case — that gate matches what
    the legacy `/case/report/generate-{investigation,activities}/...`
    routes enforce via `ac_requires_case_identifier`. Dispatch
    between investigation / activities is driven by the template's
    `report_type` so the UI doesn't have to know which generator to
    call.
    """
    try:
        template = _get_template(identifier)
    except ObjectNotFoundError:
        return response_api_not_found()

    body = request.get_json() or {}
    case_id = body.get('case_id')
    if not isinstance(case_id, int):
        return response_api_error('Missing or invalid case_id')

    safe_mode = bool(body.get('safe_mode'))

    if not ac_fast_check_current_user_has_case_access(
        case_id, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]
    ):
        # Mask "exists but you can't see it" as 404, same convention
        # as the v2 case routes.
        return response_api_not_found()

    if Cases.query.filter(Cases.case_id == case_id).first() is None:
        return response_api_not_found()

    tmp_dir = tempfile.mkdtemp()
    report_type_name = template.report_type.name if template.report_type else ''

    try:
        if report_type_name == 'Investigation':
            fpath = generate_investigation_report(case_id, template.id, safe_mode, tmp_dir)
        elif report_type_name == 'Activities':
            fpath = generate_activities_report(case_id, template.id, safe_mode, tmp_dir)
        else:
            return response_api_error(
                f"Unsupported report type '{report_type_name}' on this template"
            )
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as exc:
        return response_api_error(exc.get_message(), data=exc.get_data())

    response = send_file(fpath, as_attachment=True)
    _FILE_REMOVER.cleanup_once_done(response, tmp_dir)
    return response


# ----- Case picker for the render preview ----------------------------

@report_templates_blueprint.get('/accessible-cases')
@ac_api_requires(Permissions.server_administrator)
def list_accessible_cases() -> Response:
    """Lightweight list of cases the current user can render against.

    Returns at most 200 rows ordered by `case_id DESC`, optionally
    filtered by a `search` ILIKE on case name + SOC id. The page
    refreshes this list on every keystroke (debounced); 200 is the
    inflexion point past which a user is expected to start typing.

    We still re-check `ac_fast_check_current_user_has_case_access`
    per row even though the route is admin-gated, so an admin who
    explicitly removed themselves from a case still doesn't see it.
    """
    from sqlalchemy import or_
    query = Cases.query.with_entities(Cases.case_id, Cases.name, Cases.soc_id)
    search = (request.args.get('search') or '').strip() or None
    if search:
        needle = f'%{search}%'
        query = query.filter(or_(Cases.name.ilike(needle), Cases.soc_id.ilike(needle)))
    query = query.order_by(Cases.case_id.desc()).limit(200)

    items: List[Dict[str, Any]] = []
    for row in query.all():
        if not ac_fast_check_current_user_has_case_access(
            row.case_id, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]
        ):
            continue
        items.append({
            'case_id': row.case_id,
            'name': row.name,
            'soc_id': row.soc_id,
        })

    return response_api_success({'data': items})


# ----- Schema + lookups ----------------------------------------------

# Friendly labels + help keyed by model field name. The list endpoint
# powers the interactive editor — adding a column on
# CaseTemplateReport just needs an entry here and a render in the
# page.
_FIELD_META = {
    'name': {'label': 'Name', 'help': 'Required. Shown in the picker.'},
    'description': {'label': 'Description', 'help': "Admin-side description."},
    'naming_format': {
        'label': 'Output filename format',
        'help': 'Supports tags: %date%, %customer%, %case_name%, %code_name%.',
    },
    'language_id': {'label': 'Language', 'help': 'Used by the renderer for locale-aware formatting.'},
    'report_type_id': {
        'label': 'Report type',
        'help': "'Investigation' renders the full case export; 'Activities' renders the activity log.",
    },
}


@report_templates_blueprint.get('/schema')
@ac_api_requires(Permissions.server_administrator)
def get_report_template_schema() -> Response:
    """Editor metadata + seeded lookups in a single round-trip.

    Languages and report types are seeded at install time and only
    grow when the operator adds new ones via SQL; bundling them with
    the schema keeps the form rendering free of extra requests on
    open.
    """
    languages = [
        {'id': lang.id, 'name': lang.name, 'code': lang.code}
        for lang in Languages.query.order_by(Languages.name).all()
    ]
    report_types = [
        {'id': rt.id, 'name': rt.name}
        for rt in ReportType.query.order_by(ReportType.name).all()
    ]

    fields = [
        {'name': 'name', 'kind': 'string', 'required': True, **_FIELD_META['name']},
        {'name': 'description', 'kind': 'text', 'required': False, **_FIELD_META['description']},
        {
            'name': 'naming_format',
            'kind': 'string',
            'required': False,
            **_FIELD_META['naming_format'],
        },
        {
            'name': 'language_id',
            'kind': 'select',
            'required': True,
            'options_ref': 'languages',
            **_FIELD_META['language_id'],
        },
        {
            'name': 'report_type_id',
            'kind': 'select',
            'required': True,
            'options_ref': 'report_types',
            **_FIELD_META['report_type_id'],
        },
    ]

    return response_api_success({
        'fields': fields,
        'lookups': {
            'languages': languages,
            'report_types': report_types,
        },
        'allowed_extensions': sorted(_ALLOWED_EXTENSIONS),
        'naming_format_tags': ['%date%', '%customer%', '%case_name%', '%code_name%'],
    })


# Keep User import "used" — it's referenced indirectly through the
# CaseTemplateReport.created_by_user relationship in the serialiser
# but Python linters can't follow that.
_ = User
