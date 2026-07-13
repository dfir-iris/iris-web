#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""War-room datastore REST routes."""

from flask import Blueprint, request, send_file

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.v2.war_rooms.access import require_war_room_read
from app.blueprints.rest.v2.war_rooms.access import require_war_room_write
from app.business.war_room_datastore import (
    war_room_attached_cases,
    war_room_datastore_delete,
    war_room_datastore_get,
    war_room_datastore_list,
    war_room_datastore_open,
    war_room_datastore_save,
)
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


war_rooms_datastore_blueprint = Blueprint(
    'war_rooms_datastore_rest_v2', __name__,
    url_prefix='/<int:war_room_id>/datastore'
)


def _serialize(row):
    return {
        'file_id': row.file_id,
        'war_room_id': row.war_room_id,
        'filename': row.filename,
        'description': row.description,
        'size_bytes': row.size_bytes,
        'mime_type': row.mime_type,
        'sha256': row.sha256,
        'uploaded_at': row.uploaded_at.isoformat() if row.uploaded_at else None,
        'uploaded_by_id': row.uploaded_by_id,
        'tags': row.tags,
    }


@war_rooms_datastore_blueprint.get('')
@ac_api_requires()
def list_files(war_room_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    rows = war_room_datastore_list(war_room_id)
    attached = war_room_attached_cases(war_room_id)
    return response_api_success({
        'files': [_serialize(r) for r in rows],
        'attached_case_ids': attached,
    })


@war_rooms_datastore_blueprint.post('')
@ac_api_requires()
def upload_file(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err

    if 'file' not in request.files:
        return response_api_error('A "file" multipart field is required')
    file_storage = request.files['file']
    if not file_storage.filename:
        return response_api_error('Empty filename')

    try:
        row = war_room_datastore_save(
            war_room_id,
            file_stream=file_storage.stream,
            filename=file_storage.filename,
            mime_type=file_storage.mimetype,
            description=request.form.get('description'),
            tags=request.form.get('tags'),
            uploaded_by_id=iris_current_user.id,
        )
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())

    return response_api_created(_serialize(row))


@war_rooms_datastore_blueprint.get('/<int:file_id>')
@ac_api_requires()
def get_file_meta(war_room_id, file_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        row = war_room_datastore_get(war_room_id, file_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_serialize(row))


@war_rooms_datastore_blueprint.get('/<int:file_id>/content')
@ac_api_requires()
def download_file(war_room_id, file_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        row = war_room_datastore_get(war_room_id, file_id)
        fh = war_room_datastore_open(row)
    except ObjectNotFoundError:
        return response_api_not_found()
    return send_file(
        fh,
        mimetype=row.mime_type or 'application/octet-stream',
        as_attachment=True,
        download_name=row.filename,
    )


@war_rooms_datastore_blueprint.delete('/<int:file_id>')
@ac_api_requires()
def delete_file(war_room_id, file_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        war_room_datastore_delete(war_room_id, file_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_deleted()
