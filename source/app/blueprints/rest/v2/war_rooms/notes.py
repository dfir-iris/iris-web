#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""War-room notes REST routes."""

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
from app.business.war_room_notes import (
    war_room_note_create,
    war_room_note_delete,
    war_room_note_get,
    war_room_note_list,
    war_room_note_update,
)
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


war_rooms_notes_blueprint = Blueprint(
    'war_rooms_notes_rest_v2', __name__, url_prefix='/<int:war_room_id>/notes'
)


def _serialize(n):
    return {
        'note_id': n.note_id,
        'war_room_id': n.war_room_id,
        'title': n.title,
        'content': n.content,
        'created_at': n.created_at.isoformat() if n.created_at else None,
        'updated_at': n.updated_at.isoformat() if n.updated_at else None,
        'created_by_id': n.created_by_id,
        'updated_by_id': n.updated_by_id,
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
            war_room_id, title=raw.get('title'),
            content=raw.get('content'), created_by_id=iris_current_user.id,
        )
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
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
    try:
        note = war_room_note_update(
            war_room_id, note_id,
            title=raw.get('title'),
            content=raw.get('content'),
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
