#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""SitRep REST routes + export endpoints."""

from flask import Blueprint, Response, request, send_file, current_app
import io

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.v2.war_rooms.access import require_war_room_read
from app.blueprints.rest.v2.war_rooms.access import require_war_room_write
from app.business.war_room_chat import create_message
from app.business.war_room_sitreps import (
    sitrep_as_html,
    sitrep_as_markdown,
    sitrep_delete,
    sitrep_draft,
    sitrep_get,
    sitrep_list,
    sitrep_publish,
    sitrep_update,
)
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


war_rooms_sitreps_blueprint = Blueprint(
    'war_rooms_sitreps_rest_v2', __name__,
    url_prefix='/<int:war_room_id>/sitreps'
)


def _serialize(s, include_body=True):
    d = {
        'sitrep_id': s.sitrep_id,
        'war_room_id': s.war_room_id,
        'version': s.version,
        'title': s.title,
        'authored_by_id': s.authored_by_id,
        'authored_at': s.authored_at.isoformat() if s.authored_at else None,
        'published': bool(s.published),
        'snapshot_json': s.snapshot_json,
    }
    if include_body:
        d['body_md'] = s.body_md
    return d


def _safe_filename(name, ext):
    out = ''.join(c if c.isalnum() or c in ('-', '_') else '-' for c in (name or 'sitrep'))
    out = out.strip('-_') or 'sitrep'
    return f'{out[:100]}.{ext}'


@war_rooms_sitreps_blueprint.get('')
@ac_api_requires()
def list_sitreps(war_room_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    rows = sitrep_list(war_room_id)
    return response_api_success(data=[_serialize(s, include_body=False) for s in rows])


@war_rooms_sitreps_blueprint.post('')
@ac_api_requires()
def create_sitrep(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        sit = sitrep_draft(
            war_room_id,
            title=raw.get('title'),
            body_md=raw.get('body_md') or '',
            authored_by_id=iris_current_user.id,
        )
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_created(_serialize(sit))


@war_rooms_sitreps_blueprint.get('/<int:sitrep_id>')
@ac_api_requires()
def get_sitrep(war_room_id, sitrep_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        sit = sitrep_get(war_room_id, sitrep_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_serialize(sit))


@war_rooms_sitreps_blueprint.patch('/<int:sitrep_id>')
@ac_api_requires()
def update_sitrep(war_room_id, sitrep_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        sit = sitrep_update(war_room_id, sitrep_id,
                            title=raw.get('title'),
                            body_md=raw.get('body_md'))
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_success(_serialize(sit))


@war_rooms_sitreps_blueprint.post('/<int:sitrep_id>/publish')
@ac_api_requires()
def publish_sitrep(war_room_id, sitrep_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        sit = sitrep_publish(war_room_id, sitrep_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    # Mirror the publish event into the chat so the team sees it inline.
    try:
        create_message(
            war_room_id, iris_current_user.id,
            body=f'Published SitRep v{sit.version}: {sit.title}',
            kind='sitrep_published', ref_type='sitrep', ref_id=sit.sitrep_id,
        )
    except Exception:
        pass
    return response_api_success(_serialize(sit))


@war_rooms_sitreps_blueprint.delete('/<int:sitrep_id>')
@ac_api_requires()
def delete_sitrep(war_room_id, sitrep_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        sitrep_delete(war_room_id, sitrep_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_deleted()


@war_rooms_sitreps_blueprint.get('/<int:sitrep_id>/export.md')
@ac_api_requires()
def export_markdown(war_room_id, sitrep_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        sit = sitrep_get(war_room_id, sitrep_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    md = sitrep_as_markdown(sit)
    buf = io.BytesIO(md.encode('utf-8'))
    return send_file(
        buf,
        mimetype='text/markdown; charset=utf-8',
        as_attachment=True,
        download_name=_safe_filename(sit.title, 'md'),
    )


@war_rooms_sitreps_blueprint.get('/<int:sitrep_id>/export.html')
@ac_api_requires()
def export_html(war_room_id, sitrep_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        sit = sitrep_get(war_room_id, sitrep_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return Response(
        sitrep_as_html(sit),
        mimetype='text/html; charset=utf-8',
        headers={'Content-Disposition':
                 f'attachment; filename="{_safe_filename(sit.title, "html")}"'},
    )


@war_rooms_sitreps_blueprint.get('/<int:sitrep_id>/export.pdf')
@ac_api_requires()
def export_pdf(war_room_id, sitrep_id):
    """PDF export.

    Best-effort: if `weasyprint` or `xhtml2pdf` is installed in the
    server image we render server-side. If not, we still return the
    rich HTML with a `Content-Disposition: attachment` header that
    most browsers happily print-to-PDF — the operator still gets a
    self-contained, styled document without us shelling out to a
    binary that may not be available.
    """
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        sit = sitrep_get(war_room_id, sitrep_id)
    except ObjectNotFoundError:
        return response_api_not_found()

    html = sitrep_as_html(sit)
    filename = _safe_filename(sit.title, 'pdf')

    try:
        from weasyprint import HTML  # type: ignore
        pdf_bytes = HTML(string=html).write_pdf()
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )
    except Exception:
        pass

    try:
        from xhtml2pdf import pisa  # type: ignore
        out = io.BytesIO()
        result = pisa.CreatePDF(html, dest=out)
        if not result.err:
            out.seek(0)
            return Response(
                out.getvalue(),
                mimetype='application/pdf',
                headers={'Content-Disposition': f'attachment; filename="{filename}"'},
            )
    except Exception:
        pass

    # PDF backend unavailable. Return the rich HTML so the browser can
    # print-to-PDF — but flip the extension back to .html so users know
    # what they got.
    fallback_name = _safe_filename(sit.title, 'html')
    return Response(
        html,
        mimetype='text/html; charset=utf-8',
        headers={'Content-Disposition':
                 f'attachment; filename="{fallback_name}"',
                 'X-Pdf-Backend': 'unavailable'},
    )
