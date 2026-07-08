#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Persistence helpers for the war-room notes folder tree.

Kept thin — the business layer wraps these with activity tracking and
module hooks. This module owns the recursive-delete walk and the
revision-write dedup logic, mirroring `app/datamgmt/case/case_notes_db.py`
so the two systems evolve in parallel."""

from datetime import datetime
from typing import List

from app.datamgmt.db_operations import db_create
from app.datamgmt.db_operations import db_delete
from app.datamgmt.filtering import paginate
from app.db import db
from app.models.pagination_parameters import PaginationParameters
from app.models.war_rooms import WarRoomNote
from app.models.war_rooms import WarRoomNoteFolder
from app.models.war_rooms import WarRoomNoteRevision


def get_note(war_room_id: int, note_id: int) -> WarRoomNote:
    return WarRoomNote.query.filter_by(
        war_room_id=war_room_id, note_id=note_id
    ).first()


def get_folder(folder_id: int) -> WarRoomNoteFolder:
    return WarRoomNoteFolder.query.filter_by(id=folder_id).first()


def paginate_folders(war_room_id: int,
                     pagination_parameters: PaginationParameters):
    query = WarRoomNoteFolder.query.filter_by(war_room_id=war_room_id)
    return paginate(WarRoomNoteFolder, pagination_parameters, query)


def list_folders(war_room_id: int) -> List[WarRoomNoteFolder]:
    """Every folder for the war room, flat. The frontend hydrates the tree
    from `parent_id` client-side (same pattern as case notes)."""
    return WarRoomNoteFolder.query.filter_by(
        war_room_id=war_room_id
    ).order_by(WarRoomNoteFolder.name.asc()).all()


def delete_folder(folder: WarRoomNoteFolder) -> bool:
    """Recursively delete a folder + every note inside it + every subfolder.

    The DB has `ondelete='CASCADE'` on `war_room_note_folder.parent_id`,
    so a simple `db_delete(folder)` would already reap subfolders. But
    `WarRoomNote.folder_id` has NO cascade — we want the business layer
    to explicitly walk the subtree so revision history and any future
    per-note module hooks get a chance to fire. This mirrors
    `case_notes_db.delete_directory()`."""
    if not folder:
        return False
    for note in list(folder.notes):
        delete_note(note.note_id)
    for subfolder in list(folder.subfolders):
        delete_folder(subfolder)
    db_delete(folder)
    return True


def delete_note(note_id: int) -> None:
    """Delete a note and its revision history. The `versions`
    relationship on `WarRoomNote` uses `cascade='all, delete-orphan'`,
    so an ORM delete tears down `war_room_note_revision` rows with it."""
    note = WarRoomNote.query.filter(WarRoomNote.note_id == note_id).first()
    if note is None:
        return
    db.session.delete(note)


def write_revision(user_id: int, note: WarRoomNote) -> bool:
    """Snapshot the current note state as a new revision, unless the
    latest revision already has identical title+content. Returns True
    when a row was actually written.

    Called on create (first revision) and on every content-changing
    update — the dedup skip means back-to-back saves with no diff
    don't spam the history."""
    latest = (
        db.session.query(WarRoomNoteRevision)
        .filter_by(note_id=note.note_id)
        .order_by(WarRoomNoteRevision.revision_number.desc())
        .first()
    )
    revision_number = 1 if latest is None else latest.revision_number + 1
    if (revision_number > 1
            and latest.title == note.title
            and latest.content == note.content):
        return False
    revision = WarRoomNoteRevision(
        note_id=note.note_id,
        revision_number=revision_number,
        title=note.title,
        content=note.content,
        revised_by_id=user_id,
        revised_at=datetime.utcnow(),
    )
    db_create(revision)
    return True


def list_revisions(note_id: int):
    """Revision rows shaped for the frontend history dialog. Joins the
    `user` table so the caller doesn't have to make N+1 lookups just to
    render the author name."""
    from app.models.authorization import User
    return (
        db.session.query(
            WarRoomNoteRevision.revision_number,
            WarRoomNoteRevision.revised_at,
            User.user.label('user_name'),
        )
        .outerjoin(User, User.id == WarRoomNoteRevision.revised_by_id)
        .filter(WarRoomNoteRevision.note_id == note_id)
        .order_by(WarRoomNoteRevision.revision_number.desc())
        .all()
    )


def get_revision(note_id: int, revision_number: int) -> WarRoomNoteRevision:
    return WarRoomNoteRevision.query.filter_by(
        note_id=note_id, revision_number=revision_number
    ).first()


def count_revisions(note_id: int) -> int:
    return WarRoomNoteRevision.query.filter_by(note_id=note_id).count()
