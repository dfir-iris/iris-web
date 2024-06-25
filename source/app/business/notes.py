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
from flask_login import current_user

from marshmallow import ValidationError

from app import db
from app.business.errors import BusinessProcessingError, UnhandledBusinessError
from app.business.permissions import check_current_user_has_some_case_access_stricter
from app.datamgmt.case.case_notes_db import get_note
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel, User
from app.models import Notes, NoteVersions
from app.schema.marshables import CaseNoteSchema
from app.util import add_obj_history_entry


def _load(request_data, note_schema=None):
    try:
        if note_schema is None:
            note_schema = CaseNoteSchema()
        return note_schema.load(request_data)
    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)


def create(request_json, case_identifier):
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
        note.note_user = current_user.id
        note.note_case_id = case_identifier

        db.session.add(note)
        db.session.flush()

        note_version = NoteVersions(
            note_id=note.note_id,
            version_number=1,
            note_title=note.note_title,
            note_content=note.note_content,
            note_user=note.note_user,
            version_timestamp=datetime.utcnow()
        )
        db.session.add(note_version)

        add_obj_history_entry(note, 'created note', commit=True)
        note = call_modules_hook('on_postload_note_create', data=note, caseid=case_identifier)

        track_activity(f"created note \"{note.note_title}\"", caseid=case_identifier)

        return note

    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)

    except Exception as e:
        raise BusinessProcessingError('Unexpected error server-side', e)


def update(identifier: int = None, request_json: dict = None, case_identifier: int = None):
    """
    Update a note by its identifier.

    :param identifier: The note identifier.
    :param request_json: The request data.
    :param case_identifier: The case identifier.
    """
    check_current_user_has_some_case_access_stricter([CaseAccessLevel.full_access])

    try:
        addnote_schema = CaseNoteSchema()

        note = get_note(identifier, caseid=case_identifier)
        if not note:
            raise BusinessProcessingError("Invalid note ID for this case")

        request_data = call_modules_hook('on_preload_note_update', data=request_json, caseid=case_identifier)

        latest_version = db.session.query(
            NoteVersions
        ).filter_by(
            note_id=identifier
        ).order_by(
            NoteVersions.version_number.desc()
        ).first()
        version_number = 1 if latest_version is None else latest_version.version_number + 1

        note_version = NoteVersions(
            note_id=note.note_id,
            version_number=version_number,
            note_title=note.note_title,
            note_content=note.note_content,
            note_user=note.note_user,
            version_timestamp=datetime.utcnow()
        )
        db.session.add(note_version)
        db.session.commit()

        request_data['note_id'] = identifier
        addnote_schema.load(request_data, partial=True, instance=note)
        note.update_date = datetime.utcnow()
        note.user_id = current_user.id

        add_obj_history_entry(note, 'updated note', commit=True)
        note = call_modules_hook('on_postload_note_update', data=note, caseid=case_identifier)

        track_activity(f"updated note \"{note.note_title}\"", caseid=case_identifier)

        return note

    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)

    except Exception as e:
        raise UnhandledBusinessError('Unexpected error server-side', str(e))


def list_note_revisions(identifier: int = None, case_identifier: int = None):
    """
    List the revisions of a note by its identifier.

    :param identifier: The note identifier.
    :param case_identifier: The case identifier.

    :return: The note history.
    """

    try:

        note = get_note(identifier, caseid=case_identifier)
        if not note:
            raise BusinessProcessingError("Invalid note ID for this case")

        note_versions = NoteVersions.query.with_entities(
            NoteVersions.version_number,
            NoteVersions.version_timestamp,
            NoteVersions.note_user
        ).order_by(
            NoteVersions.version_number.desc()
        ).filter(
            NoteVersions.note_id==identifier
        ).all()

        return note_versions

    except ValidationError as e:
        raise BusinessProcessingError('Data error', e.messages)

    except Exception as e:
        raise UnhandledBusinessError('Unexpected error server-side', str(e))