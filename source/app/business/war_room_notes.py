#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Business layer for war-room notes."""

import datetime

from app.db import db
from app.iris_engine.utils.tracker import track_activity
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.war_rooms import WarRoomNote


def _validate_title(title):
    if not isinstance(title, str) or not title.strip():
        raise BusinessProcessingError('Note title is required')
    return title.strip()[:512]


def war_room_note_list(war_room_id):
    return (
        WarRoomNote.query
        .filter_by(war_room_id=war_room_id)
        .order_by(WarRoomNote.updated_at.desc())
        .all()
    )


def war_room_note_get(war_room_id, note_id):
    row = WarRoomNote.query.filter_by(
        war_room_id=war_room_id, note_id=note_id
    ).first()
    if row is None:
        raise ObjectNotFoundError()
    return row


def war_room_note_create(war_room_id, title, content=None, created_by_id=None):
    title = _validate_title(title)
    note = WarRoomNote()
    note.war_room_id = war_room_id
    note.title = title
    note.content = content
    note.created_by_id = created_by_id
    note.updated_by_id = created_by_id
    db.session.add(note)
    db.session.commit()
    track_activity(f'created war room note "{note.title}"', war_room_id=war_room_id)
    return note


def war_room_note_update(war_room_id, note_id, title=None, content=None,
                         updated_by_id=None):
    note = war_room_note_get(war_room_id, note_id)
    if title is not None:
        note.title = _validate_title(title)
    if content is not None:
        note.content = content
    note.updated_at = datetime.datetime.utcnow()
    note.updated_by_id = updated_by_id
    db.session.commit()
    track_activity(f'updated war room note "{note.title}"', war_room_id=war_room_id)
    return note


def war_room_note_delete(war_room_id, note_id):
    note = war_room_note_get(war_room_id, note_id)
    title = note.title
    db.session.delete(note)
    db.session.commit()
    track_activity(f'deleted war room note "{title}"', war_room_id=war_room_id)
