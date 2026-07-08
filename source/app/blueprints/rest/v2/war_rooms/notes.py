#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""War-room notes REST routes.

Notes live in a folder tree owned by the war room (see
`war_rooms_notes_folders_blueprint` in `notes_folders.py`). This module
covers the note CRUD + revision-history endpoints. Folder CRUD is next
door so the URL surface stays flat: everything mounts under
`/api/v2/war-rooms/{id}/`.
"""

from flask import Blueprint, request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.v2.war_rooms.access import require_war_room_read
from app.blueprints.rest.v2.war_rooms.access import require_war_room_write
from app.business.war_room_chat import emit_system_event
from app.business.war_room_notes import _UNSET
from app.business.war_room_notes import war_room_note_create
from app.business.war_room_notes import war_room_note_delete
from app.business.war_room_notes import war_room_note_delete_revision
from app.business.war_room_notes import war_room_note_get
from app.business.war_room_notes import war_room_note_get_revision
from app.business.war_room_notes import war_room_note_list
from app.business.war_room_notes import war_room_note_list_revisions
from app.business.war_room_notes import war_room_note_restore_revision
from app.business.war_room_notes import war_room_note_update
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


war_rooms_notes_blueprint = Blueprint(
    'war_rooms_notes_rest_v2', __name__, url_prefix='/<int:war_room_id>/notes'
)


def _serialize(n):
    return {
        'note_id': n.note_id,
        'war_room_id': n.war_room_id,
        'folder_id': n.folder_id,
        'title': n.title,
        'content': n.content,
        'created_at': n.created_at.isoformat() if n.created_at else None,
        'updated_at': n.updated_at.isoformat() if n.updated_at else None,
        'created_by_id': n.created_by_id,
        'updated_by_id': n.updated_by_id,
    }


def _serialize_revision_row(row):
    """Rows come from `list_revisions` as named tuples of
    (revision_number, revised_at, user_name)."""
    return {
        'revision_number': row.revision_number,
        'revised_at': row.revised_at.isoformat() if row.revised_at else None,
        'user_name': row.user_name,
    }


def _serialize_revision(rev):
    return {
        'revision_number': rev.revision_number,
        'title': rev.title,
        'content': rev.content,
        'revised_at': rev.revised_at.isoformat() if rev.revised_at else None,
        'revised_by_id': rev.revised_by_id,
    }


@war_rooms_notes_blueprint.get('')
@ac_api_requires()
def list_notes(war_room_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    return response_api_success(data=[_serialize(n) for n in war_room_note_list(war_room_id)])


@war_rooms_notes_blueprint.post('')
@ac_api_requires()
def create_note(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        note = war_room_note_create(
            war_room_id,
            title=raw.get('title'),
            content=raw.get('content'),
            folder_id=raw.get('folder_id'),
            created_by_id=iris_current_user.id,
        )
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    emit_system_event(
        war_room_id, 'note',
        f'Created note: {note.title}',
        author_id=iris_current_user.id,
        ref_type='war_room_note', ref_id=note.note_id,
    )
    return response_api_created(_serialize(note))


@war_rooms_notes_blueprint.get('/<int:note_id>')
@ac_api_requires()
def get_note(war_room_id, note_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        note = war_room_note_get(war_room_id, note_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_serialize(note))


@war_rooms_notes_blueprint.patch('/<int:note_id>')
@ac_api_requires()
def update_note(war_room_id, note_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    # `folder_id` in the body is meaningful even when set to `null` (move
    # to root). Only pass it through to the business layer if the caller
    # explicitly included the key; otherwise leave the folder alone.
    folder_kwarg = raw['folder_id'] if 'folder_id' in raw else _UNSET
    try:
        note = war_room_note_update(
            war_room_id, note_id,
            title=raw.get('title'),
            content=raw.get('content'),
            folder_id=folder_kwarg,
            updated_by_id=iris_current_user.id,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_success(_serialize(note))


@war_rooms_notes_blueprint.delete('/<int:note_id>')
@ac_api_requires()
def delete_note(war_room_id, note_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        war_room_note_delete(war_room_id, note_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_deleted()


# ---------------------------------------------------------------------------
# Revision history
# ---------------------------------------------------------------------------

@war_rooms_notes_blueprint.get('/<int:note_id>/revisions')
@ac_api_requires()
def list_revisions(war_room_id, note_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        rows = war_room_note_list_revisions(war_room_id, note_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(data=[_serialize_revision_row(r) for r in rows])


@war_rooms_notes_blueprint.get('/<int:note_id>/revisions/<int:revision_number>')
@ac_api_requires()
def get_revision(war_room_id, note_id, revision_number):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        revision = war_room_note_get_revision(war_room_id, note_id, revision_number)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_serialize_revision(revision))


@war_rooms_notes_blueprint.delete('/<int:note_id>/revisions/<int:revision_number>')
@ac_api_requires()
def delete_revision(war_room_id, note_id, revision_number):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        war_room_note_delete_revision(war_room_id, note_id, revision_number)
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_deleted()


@war_rooms_notes_blueprint.post('/<int:note_id>/revisions/<int:revision_number>/restore')
@ac_api_requires()
def restore_revision(war_room_id, note_id, revision_number):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        note = war_room_note_restore_revision(
            war_room_id, note_id, revision_number,
            updated_by_id=iris_current_user.id,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_success(_serialize(note))
