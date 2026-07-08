#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""War-room notes folder REST routes.

Companion to `notes.py` — this owns the folder tree. Same URL prefix
convention (`/<war_room_id>/notes-folders`) as the case-notes
`/notes-directories` endpoints, but "folder" is the term the frontend
uses so we prefer it here (case-notes still says "directories" for
legacy reasons).

Every endpoint is gated by the war-room ACL helpers — NOT the case
ACL — because war rooms live in their own permission model
(`WarRoomAccessLevel`).
"""

from flask import Blueprint, request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.v2.war_rooms.access import require_war_room_read
from app.blueprints.rest.v2.war_rooms.access import require_war_room_write
from app.business.war_room_note_folders import verify_parent_folder
from app.business.war_room_note_folders import war_room_note_folders_create
from app.business.war_room_note_folders import war_room_note_folders_delete
from app.business.war_room_note_folders import war_room_note_folders_get
from app.business.war_room_note_folders import war_room_note_folders_update
from app.datamgmt.war_rooms.war_room_notes_db import list_folders
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.war_rooms import WarRoomNoteFolder


war_rooms_notes_folders_blueprint = Blueprint(
    'war_rooms_notes_folders_rest_v2', __name__,
    url_prefix='/<int:war_room_id>/notes-folders',
)


def _serialize(folder: WarRoomNoteFolder) -> dict:
    return {
        'id': folder.id,
        'name': folder.name,
        'war_room_id': folder.war_room_id,
        'parent_id': folder.parent_id,
        'created_at': folder.created_at.isoformat() if folder.created_at else None,
        'updated_at': folder.updated_at.isoformat() if folder.updated_at else None,
    }


def _validate_name(raw) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise BusinessProcessingError('Folder name is required')
    return raw.strip()[:512]


@war_rooms_notes_folders_blueprint.get('')
@ac_api_requires()
def list_notes_folders(war_room_id):
    """Flat list of every folder in the war room. The frontend hydrates
    the tree client-side from `parent_id` — same pattern as case notes."""
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    return response_api_success(
        data=[_serialize(f) for f in list_folders(war_room_id)]
    )


@war_rooms_notes_folders_blueprint.post('')
@ac_api_requires()
def create_notes_folder(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        name = _validate_name(raw.get('name'))
        parent_id = verify_parent_folder(
            raw.get('parent_id'), war_room_id, current_id=None,
        )
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    folder = WarRoomNoteFolder(
        name=name, war_room_id=war_room_id, parent_id=parent_id,
    )
    folder = war_room_note_folders_create(folder)
    return response_api_created(_serialize(folder))


@war_rooms_notes_folders_blueprint.get('/<int:folder_id>')
@ac_api_requires()
def get_notes_folder(war_room_id, folder_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        folder = war_room_note_folders_get(folder_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    if folder.war_room_id != war_room_id:
        # 404 rather than 403 so folder ids can't be enumerated across war rooms.
        return response_api_not_found()
    return response_api_success(_serialize(folder))


@war_rooms_notes_folders_blueprint.put('/<int:folder_id>')
@ac_api_requires()
def update_notes_folder(war_room_id, folder_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        folder = war_room_note_folders_get(folder_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    if folder.war_room_id != war_room_id:
        return response_api_not_found()
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        if 'name' in raw:
            folder.name = _validate_name(raw['name'])
        if 'parent_id' in raw:
            folder.parent_id = verify_parent_folder(
                raw['parent_id'], war_room_id, current_id=folder.id,
            )
        folder = war_room_note_folders_update(folder)
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_success(_serialize(folder))


@war_rooms_notes_folders_blueprint.delete('/<int:folder_id>')
@ac_api_requires()
def delete_notes_folder(war_room_id, folder_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        folder = war_room_note_folders_get(folder_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    if folder.war_room_id != war_room_id:
        return response_api_not_found()
    war_room_note_folders_delete(folder)
    return response_api_deleted()
