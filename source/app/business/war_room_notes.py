#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Business layer for war-room notes."""

import datetime

from app.datamgmt.war_rooms.war_room_notes_db import count_revisions
from app.datamgmt.war_rooms.war_room_notes_db import get_folder
from app.datamgmt.war_rooms.war_room_notes_db import get_revision
from app.datamgmt.war_rooms.war_room_notes_db import list_revisions
from app.datamgmt.war_rooms.war_room_notes_db import write_revision
from app.db import db
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.war_rooms import WarRoomNote
from app.models.war_rooms import WarRoomNoteRevision


def _validate_title(title):
    if not isinstance(title, str) or not title.strip():
        raise BusinessProcessingError('Note title is required')
    return title.strip()[:512]


def _fire_mention_notifications(note, actor_id, is_update):
    """Notify war-room members mentioned in a note.

    Silent on failure — a broken notification pipeline must not fail a
    note write."""
    try:
        from app.iris_engine.notifications.mentions import resolve_mentions_to_user_ids
        from app.iris_engine.notifications.service import notify_many
        from app.models.war_rooms import WarRoomMember

        mentioned = resolve_mentions_to_user_ids(note.content, note.war_room_id)
        if not mentioned:
            return

        member_ids = {
            row.user_id for row in
            WarRoomMember.query
            .filter(WarRoomMember.war_room_id == note.war_room_id)
            .filter(WarRoomMember.user_id.in_(mentioned))
            .all()
        }
        if not member_ids:
            return

        verb = 'updated' if is_update else 'created'
        notify_many(
            user_ids=list(member_ids),
            event_type='mention',
            title=f'You were mentioned in a war-room note',
            body=f'{verb}: {note.title}',
            link=f'/war-rooms/{note.war_room_id}/notes?note={note.note_id}',
            source_type='war_room_note',
            source_id=note.note_id,
            exclude_user_ids=[actor_id] if actor_id else [],
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            'war-room note mention notification failed')


def _resolve_folder_id(war_room_id, folder_id):
    """Coerce a folder-id payload to `None | int` and enforce that the
    folder (if given) belongs to the same war room. Keeps notes from
    leaking across war rooms via a spoofed `folder_id`."""
    if folder_id is None:
        return None
    folder = get_folder(int(folder_id))
    if folder is None or folder.war_room_id != war_room_id:
        raise BusinessProcessingError('Invalid folder id for this war room')
    return folder.id


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


def war_room_note_create(war_room_id, title, content=None,
                         folder_id=None, created_by_id=None):
    title = _validate_title(title)
    resolved_folder = _resolve_folder_id(war_room_id, folder_id)
    note = WarRoomNote()
    note.war_room_id = war_room_id
    note.title = title
    note.content = content
    note.folder_id = resolved_folder
    note.created_by_id = created_by_id
    note.updated_by_id = created_by_id
    db.session.add(note)
    db.session.flush()
    # Seed revision #1 so history is complete from the first save. Any
    # later dedup skip on empty edits is fine — we've captured the baseline.
    write_revision(created_by_id, note)
    db.session.commit()
    track_activity(f'created war room note "{note.title}"', war_room_id=war_room_id)
    _fire_mention_notifications(note, created_by_id, is_update=False)
    note = call_modules_hook('on_postload_war_room_note_create', note)
    return note


_UNSET = object()


def war_room_note_update(war_room_id, note_id, title=None, content=None,
                         folder_id=_UNSET, updated_by_id=None):
    """Update a note. `folder_id` uses a sentinel default so callers can
    distinguish "don't change the folder" (omit) from "move to root"
    (pass `None` explicitly)."""
    note = war_room_note_get(war_room_id, note_id)
    prior_content = note.content
    if title is not None:
        note.title = _validate_title(title)
    if content is not None:
        note.content = content
    if folder_id is not _UNSET:
        note.folder_id = _resolve_folder_id(war_room_id, folder_id)
    note.updated_at = datetime.datetime.utcnow()
    note.updated_by_id = updated_by_id
    # Snapshot before commit — the dedup inside `write_revision` skips
    # no-op saves so pure metadata edits (folder move) don't create
    # revisions with identical title+content.
    write_revision(updated_by_id, note)
    db.session.commit()
    track_activity(f'updated war room note "{note.title}"', war_room_id=war_room_id)
    # Only fire when the body actually changed — pure title / folder edits
    # shouldn't re-page every mentioned user.
    if content is not None and content != prior_content:
        _fire_mention_notifications(note, updated_by_id, is_update=True)
    note = call_modules_hook('on_postload_war_room_note_update', note)
    return note


def war_room_note_delete(war_room_id, note_id):
    note = war_room_note_get(war_room_id, note_id)
    title = note.title
    db.session.delete(note)
    db.session.commit()
    track_activity(f'deleted war room note "{title}"', war_room_id=war_room_id)
    call_modules_hook('on_postload_war_room_note_delete',
                      {'war_room_id': war_room_id, 'note_id': note_id})


def war_room_note_list_revisions(war_room_id, note_id):
    """Return revision-row tuples for the note. Access is gated at the
    route layer via `require_war_room_read`; we still re-check the note
    belongs to the war room so a caller can't enumerate revisions
    across war rooms by note id."""
    war_room_note_get(war_room_id, note_id)  # raises if cross-tenant
    return list_revisions(note_id)


def war_room_note_get_revision(war_room_id, note_id,
                               revision_number) -> WarRoomNoteRevision:
    war_room_note_get(war_room_id, note_id)
    revision = get_revision(note_id, revision_number)
    if revision is None:
        raise ObjectNotFoundError()
    return revision


def war_room_note_delete_revision(war_room_id, note_id, revision_number):
    war_room_note_get(war_room_id, note_id)
    revision = get_revision(note_id, revision_number)
    if revision is None:
        raise ObjectNotFoundError()
    # Keep at least one revision so history never shows "no versions
    # ever existed" for a note that was clearly created and edited.
    if count_revisions(note_id) <= 1:
        raise BusinessProcessingError('Cannot delete the only revision of a note')
    db.session.delete(revision)
    db.session.commit()
    track_activity(
        f'deleted revision #{revision_number} of note {note_id}',
        war_room_id=war_room_id,
    )


def war_room_note_restore_revision(war_room_id, note_id, revision_number,
                                   updated_by_id=None) -> WarRoomNote:
    """Snapshot the current note state as a NEW revision, then overwrite
    the note with the target revision. Restore is undoable — the state
    just before restore is preserved as the newest revision."""
    note = war_room_note_get(war_room_id, note_id)
    revision = get_revision(note_id, revision_number)
    if revision is None:
        raise ObjectNotFoundError()

    write_revision(updated_by_id, note)

    note.title = revision.title
    note.content = revision.content
    note.updated_at = datetime.datetime.utcnow()
    note.updated_by_id = updated_by_id
    db.session.commit()
    track_activity(
        f'restored revision #{revision_number} of note "{note.title}"',
        war_room_id=war_room_id,
    )
    return note
