#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

from datetime import datetime

from app.db import db
from app.datamgmt.persistence_error import PersistenceError
from app.blueprints.iris_user import iris_current_user
from app.logger import logger
from app.models.errors import BusinessProcessingError
from app.models.errors import UnhandledBusinessError
from app.models.errors import ObjectNotFoundError
from app.datamgmt.case.case_notes_db import search_notes_in_case
from app.datamgmt.case.case_notes_db import get_note
from app.datamgmt.case.case_notes_db import update_note_revision
from app.datamgmt.case.case_notes_db import delete_note
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.models import NoteRevisions
from app.models.models import Notes
from app.models.authorization import User
from app.util import add_obj_history_entry


def notes_search(case_identifier, search_input):
    return search_notes_in_case(case_identifier, search_input)


def notes_create(note: Notes, case_identifier):
    try:
        note.note_creationdate = datetime.utcnow()
        note.note_lastupdate = datetime.utcnow()
        note.note_user = iris_current_user.id
        note.note_case_id = case_identifier

        db.session.add(note)
        db.session.flush()

        note_revision = NoteRevisions(
            note_id=note.note_id,
            revision_number=1,
            note_title=note.note_title,
            note_content=note.note_content,
            note_user=note.note_user,
            revision_timestamp=datetime.utcnow()
        )
        db.session.add(note_revision)

        add_obj_history_entry(note, 'created note', commit=True)
        note = call_modules_hook('on_postload_note_create', note, caseid=case_identifier)

        track_activity(f'created note "{note.note_title}"', caseid=case_identifier)

        return note

    except Exception as e:
        raise BusinessProcessingError('Unexpected error server-side', e)


def notes_get(identifier) -> Notes:
    note = get_note(identifier)
    if not note:
        raise ObjectNotFoundError()

    return note


def notes_update(user, note: Notes):
    try:
        if not update_note_revision(user.id, note):
            logger.debug(f'Note {note.note_id} has not changed, skipping versioning')

        note.update_date = datetime.utcnow()
        note.user_id = iris_current_user.id

        add_obj_history_entry(note, 'updated note', commit=True)
        note = call_modules_hook('on_postload_note_update', note, caseid=note.note_case_id)

        track_activity(f'updated note "{note.note_title}"', caseid=note.note_case_id)

        return note

    except PersistenceError as e:
        logger.error(e)
        raise BusinessProcessingError('Invalid values provided for update')

    except Exception as e:
        raise UnhandledBusinessError('Unexpected error server-side', str(e))


def notes_delete(note: Notes):
    call_modules_hook('on_preload_note_delete', note.note_id, caseid=note.note_case_id)
    delete_note(note.note_id, note.note_case_id)
    call_modules_hook('on_postload_note_delete', note.note_id, caseid=note.note_case_id)

    track_activity(f'deleted note "{note.note_title}"', caseid=note.note_case_id)


def notes_list_revisions(identifier: int):
    try:
        note = get_note(identifier)
        if not note:
            raise BusinessProcessingError("Invalid note ID for this case")

        note_versions = NoteRevisions.query.with_entities(
            NoteRevisions.revision_number,
            NoteRevisions.revision_timestamp,
            User.name.label('user_name')
        ).join(
            User, NoteRevisions.note_user == User.id
        ).order_by(
            NoteRevisions.revision_number.desc()
        ).filter(
            NoteRevisions.note_id == identifier
        ).all()

        return note_versions

    except Exception as e:
        raise UnhandledBusinessError('Unexpected error server-side', str(e))


def notes_get_revision(identifier: int, revision_number: int):
    try:
        note = get_note(identifier)
        if not note:
            raise BusinessProcessingError("Invalid note ID for this case")

        note_revision = NoteRevisions.query.filter(
            NoteRevisions.note_id == identifier,
            NoteRevisions.revision_number == revision_number
        ).first()

        return note_revision

    except Exception as e:
        raise UnhandledBusinessError('Unexpected error server-side', str(e))


def notes_delete_revision(identifier: int, revision_number: int):
    try:
        note = get_note(identifier)
        if not note:
            raise BusinessProcessingError('Invalid note ID for this case')

        note_revision = NoteRevisions.query.filter(
            NoteRevisions.note_id == identifier,
            NoteRevisions.revision_number == revision_number
        ).first()

        if not note_revision:
            raise BusinessProcessingError('Invalid note revision number')

        db.session.delete(note_revision)
        db.session.commit()

        track_activity(f'deleted note revision {revision_number} of note "{note.note_title}"', caseid=note.note_case_id)

    except Exception as e:
        raise UnhandledBusinessError('Unexpected error server-side', str(e))
