#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Business layer for the war-room notes folder tree.

Mirror of `app/business/notes_directories.py`. Recursive delete lives
in `datamgmt/war_rooms/war_room_notes_db.py`; this file is a thin
CRUD/activity wrapper. Ancestry-walking cycle detection is provided so
the schema validator can reject move-into-descendant before any commit.
"""

from datetime import datetime
from typing import Optional

from app.datamgmt.war_rooms.war_room_notes_db import delete_folder
from app.datamgmt.war_rooms.war_room_notes_db import get_folder
from app.datamgmt.war_rooms.war_room_notes_db import paginate_folders
from app.db import db
from app.iris_engine.utils.tracker import track_activity
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.pagination_parameters import PaginationParameters
from app.models.war_rooms import WarRoomNoteFolder


def war_room_note_folders_filter(war_room_id: int,
                                 pagination_parameters: PaginationParameters):
    return paginate_folders(war_room_id, pagination_parameters)


def war_room_note_folders_get(identifier: int) -> WarRoomNoteFolder:
    folder = get_folder(identifier)
    if folder is None:
        raise ObjectNotFoundError()
    return folder


def war_room_note_folders_create(folder: WarRoomNoteFolder) -> WarRoomNoteFolder:
    db.session.add(folder)
    db.session.commit()
    track_activity(
        f'created war-room note folder "{folder.name}"',
        war_room_id=folder.war_room_id,
    )
    return folder


def war_room_note_folders_update(folder: WarRoomNoteFolder) -> WarRoomNoteFolder:
    folder.updated_at = datetime.utcnow()
    db.session.commit()
    track_activity(
        f'updated war-room note folder "{folder.name}"',
        war_room_id=folder.war_room_id,
    )
    return folder


def war_room_note_folders_delete(folder: WarRoomNoteFolder) -> None:
    war_room_id = folder.war_room_id
    name = folder.name
    delete_folder(folder)
    db.session.commit()
    track_activity(
        f'deleted war-room note folder "{name}"',
        war_room_id=war_room_id,
    )


def verify_parent_folder(parent_id: Optional[int], war_room_id: int,
                         current_id: Optional[int] = None) -> Optional[int]:
    """Validate a `parent_id` for a folder that lives in `war_room_id`.

    Returns the parent id unchanged when valid, raises
    `BusinessProcessingError` otherwise.

      * `parent_id=None` → root-level (always fine).
      * `current_id=None` → creating a fresh folder (only the parent's
        war-room scope needs checking).
      * `current_id` set → rename/move; walk the parent's ancestry to
        make sure we're not moving the folder under one of its own
        descendants (that's the cycle the case-notes validator misses).

    This helper is deliberately loud on failure — schema validators
    catch `BusinessProcessingError` and turn it into a 400.
    """
    if parent_id is None:
        return None

    parent = WarRoomNoteFolder.query.filter_by(id=parent_id).first()
    if parent is None or parent.war_room_id != war_room_id:
        raise BusinessProcessingError('Invalid parent folder id')

    if current_id is None:
        return parent_id

    if int(parent_id) == int(current_id):
        raise BusinessProcessingError('Folder cannot be its own parent')

    # Walk parent -> grandparent -> ... up to root; if we hit the folder
    # we're editing at any depth, the move would create a cycle.
    cursor = parent
    seen = set()
    while cursor is not None:
        if cursor.id in seen:
            # Defensive: shouldn't happen given the FK cycle check, but
            # if the DB is somehow inconsistent we don't want an infinite
            # loop under a validation call.
            raise BusinessProcessingError('Cycle detected in folder tree')
        seen.add(cursor.id)
        if cursor.id == int(current_id):
            raise BusinessProcessingError(
                'Folder cannot be moved into one of its own descendants'
            )
        cursor = cursor.parent

    return parent_id
