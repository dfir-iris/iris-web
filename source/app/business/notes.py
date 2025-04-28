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
from marshmallow import ValidationError

from app import db
from app.iris_engine.access_control.iris_user import iris_current_user
from app.logger import logger
from app.business.errors import BusinessProcessingError
from app.business.errors import UnhandledBusinessError
from app.business.errors import ObjectNotFoundError
from app.datamgmt.case.case_notes_db import get_note
from app.datamgmt.case.case_notes_db import delete_note
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.models import NoteRevisions
from app.models.models import Notes
from app.models.authorization import User
from app.schema.marshables import CaseNoteSchema
from app.util import add_obj_history_entry


def _load(request_data):
    try:
        note_schema = CaseNoteSchema()
        return note_schema.load(request_data)
    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)


def notes_create(request_json, case_identifier):
    """
    Create a note.

    :param request_json: The request data.
    :param case_identifier: The case identifier.
    """
    try:
        request_data = call_modules_hook('on_preload_note_create', data=request_json, caseid=case_identifier)
        note_schema = CaseNoteSchema()
        note_schema.verify_directory_id(request_data, caseid=case_identifier)

        note = _load(request_data)

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
        note = call_modules_hook('on_postload_note_create', data=note, caseid=case_identifier)

        track_activity(f"created note \"{note.note_title}\"", caseid=case_identifier)

        return note

    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)

    except Exception as e:
        raise BusinessProcessingError('Unexpected error server-side', e)


def notes_get(identifier) -> Notes:
    note = get_note(identifier)
    if not note:
        raise ObjectNotFoundError()

    return note


def notes_update(note: Notes, request_json: dict):
    try:
        addnote_schema = CaseNoteSchema()

        request_data = call_modules_hook('on_preload_note_update', data=request_json, caseid=note.note_case_id)

        latest_version = db.session.query(
            NoteRevisions
        ).filter_by(
            note_id=note.note_id
        ).order_by(
            NoteRevisions.revision_number.desc()
        ).first()
        revision_number = 1 if latest_version is None else latest_version.revision_number + 1
        no_changes = False

        if revision_number > 1:
            if latest_version.note_title == request_data.get('note_title') and latest_version.note_content == request_data.get('note_content'):
                no_changes = True
                logger.debug(f'Note {note.note_id} has not changed, skipping versioning')

        if not no_changes:
            note_version = NoteRevisions(
                note_id=note.note_id,
                revision_number=revision_number,
                note_title=note.note_title,
                note_content=note.note_content,
                note_user=iris_current_user.id,
                revision_timestamp=datetime.utcnow()
            )
            db.session.add(note_version)
            db.session.commit()

        request_data['note_id'] = note.note_id
        addnote_schema.load(request_data, partial=True, instance=note)
        note.update_date = datetime.utcnow()
        note.user_id = iris_current_user.id

        add_obj_history_entry(note, 'updated note', commit=True)
        note = call_modules_hook('on_postload_note_update', data=note, caseid=note.note_case_id)

        track_activity(f'updated note "{note.note_title}"', caseid=note.note_case_id)

        return note

    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)

    except Exception as e:
        raise UnhandledBusinessError('Unexpected error server-side', str(e))


def notes_delete(note: Notes):
    call_modules_hook('on_preload_note_delete', data=note.note_id, caseid=note.note_case_id)
    delete_note(note.note_id, note.note_case_id)
    call_modules_hook('on_postload_note_delete', data=note.note_id, caseid=note.note_case_id)

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

    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)

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

    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)

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

    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)

    except Exception as e:
        raise UnhandledBusinessError('Unexpected error server-side', str(e))
