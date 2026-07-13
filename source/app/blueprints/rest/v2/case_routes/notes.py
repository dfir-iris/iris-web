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

from marshmallow import ValidationError
from flask import Blueprint
from flask import request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.schema.marshables import CaseNoteRevisionSchema
from app.schema.marshables import CaseNoteSchema
from app.models.authorization import CaseAccessLevel
from app.models.models import Notes
from app.business.notes import notes_create
from app.business.notes import notes_get
from app.business.notes import notes_update
from app.business.notes import notes_delete
from app.business.notes import notes_delete_revision
from app.business.notes import notes_get_revision
from app.business.notes import notes_list_revisions
from app.business.notes import notes_restore_revision
from app.business.notes import notes_search
from app.business.cases import cases_exists
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.iris_engine.module_handler.module_handler import call_deprecated_on_preload_modules_hook
from app.blueprints.iris_user import iris_current_user


class NotesOperations:

    def __init__(self):
        self._schema = CaseNoteSchema()

    def _load(self, request_data):
        try:
            return self._schema.load(request_data)
        except ValidationError as e:
            raise BusinessProcessingError('Data error', e.messages)

    @staticmethod
    def _check_note_and_case_identifier_match(note: Notes, case_identifier):
        if note.note_case_id != case_identifier:
            raise ObjectNotFoundError

    @staticmethod
    def _check_case_access(case_identifier, access_levels):
        if not cases_exists(case_identifier):
            return response_api_not_found()

        if not ac_fast_check_current_user_has_case_access(case_identifier, access_levels):
            return ac_api_return_access_denied(caseid=case_identifier)

        return None

    def list(self, case_identifier):
        access_error = self._check_case_access(
            case_identifier,
            [CaseAccessLevel.read_only, CaseAccessLevel.full_access]
        )
        if access_error:
            return access_error

        try:
            notes = (
                Notes.query
                .filter(Notes.note_case_id == case_identifier)
                .order_by(Notes.note_id.asc())
                .all()
            )

            result = self._schema.dump(notes, many=True)
            return response_api_success(result)

        except ValidationError as e:
            return response_api_error('Data error', e.messages)

        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def search(self, case_identifier):
        access_error = self._check_case_access(
            case_identifier,
            [CaseAccessLevel.read_only, CaseAccessLevel.full_access]
        )
        if access_error:
            return access_error

        try:
            search_input = request.args.get('search_input')
            if search_input is None or not search_input.strip():
                return response_api_error(
                    'Data error',
                    data={'search_input': ['Missing or blank search_input query parameter']}
                )

            notes = notes_search(case_identifier, search_input.strip())

            result = self._schema.dump(notes, many=True)
            return response_api_success(result)

        except ValidationError as e:
            return response_api_error('Data error', e.messages)

        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def create(self, case_identifier):
        if not cases_exists(case_identifier):
            return response_api_not_found()

        if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        try:
            request_data = call_deprecated_on_preload_modules_hook('note_create', request.get_json(),
                                                                   case_identifier)

            note_schema = CaseNoteSchema()
            note_schema.verify_directory_id(request_data, caseid=case_identifier)

            note = self._load(request_data)

            note = notes_create(note, case_identifier)

            return response_api_created(self._schema.dump(note))

        except ValidationError as e:
            return response_api_error('Data error', e.messages)

        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def get(self, case_identifier, identifier):
        try:
            note = notes_get(identifier)
            self._check_note_and_case_identifier_match(note, case_identifier)

            if not ac_fast_check_current_user_has_case_access(note.note_case_id,
                                                              [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=note.note_case_id)

            result = self._schema.dump(note)
            return response_api_success(result)
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())

    def update(self, case_identifier, identifier):
        try:
            note = notes_get(identifier)
            if not ac_fast_check_current_user_has_case_access(note.note_case_id, [CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=note.note_case_id)
            self._check_note_and_case_identifier_match(note, case_identifier)

            request_data = call_deprecated_on_preload_modules_hook('note_update', request.get_json(),
                                                                   note.note_case_id)
            request_data['note_id'] = note.note_id
            self._schema.load(request_data, partial=True, instance=note)
            note = notes_update(iris_current_user, note)

            schema = CaseNoteSchema()
            result = schema.dump(note)
            return response_api_success(result)

        except ValidationError as e:
            return response_api_error('Data error', e.normalized_messages())

        except ObjectNotFoundError:
            return response_api_not_found()

        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def delete(self, case_identifier, identifier):
        try:
            note = notes_get(identifier)
            if not ac_fast_check_current_user_has_case_access(note.note_case_id, [CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=note.note_case_id)
            self._check_note_and_case_identifier_match(note, case_identifier)

            notes_delete(note)
            return response_api_deleted()

        except ObjectNotFoundError:
            return response_api_not_found()

    # ------- Revisions ---------------------------------------------------
    # Brought back from the legacy `/case/notes/<id>/revisions/...`
    # surface so the new SPA can show note history again. Read access
    # only needs `read_only` on the case; restore / delete a revision
    # require `full_access` because they mutate state visible to
    # everyone on the case.
    #
    # `notes_list_revisions` returns a SQLAlchemy `with_entities` row
    # set rather than ORM instances — the legacy code dumps that
    # straight through the schema, so we do the same.

    def list_revisions(self, case_identifier, identifier):
        try:
            note = notes_get(identifier)
            self._check_note_and_case_identifier_match(note, case_identifier)
            if not ac_fast_check_current_user_has_case_access(
                note.note_case_id, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]
            ):
                return ac_api_return_access_denied(caseid=note.note_case_id)

            revisions = notes_list_revisions(identifier)
            schema = CaseNoteRevisionSchema(many=True)
            return response_api_success(schema.dump(revisions))

        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def get_revision(self, case_identifier, identifier, revision_number):
        try:
            note = notes_get(identifier)
            self._check_note_and_case_identifier_match(note, case_identifier)
            if not ac_fast_check_current_user_has_case_access(
                note.note_case_id, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]
            ):
                return ac_api_return_access_denied(caseid=note.note_case_id)

            revision = notes_get_revision(identifier, revision_number)
            if revision is None:
                return response_api_not_found()
            return response_api_success(CaseNoteRevisionSchema().dump(revision))

        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def delete_revision(self, case_identifier, identifier, revision_number):
        try:
            note = notes_get(identifier)
            self._check_note_and_case_identifier_match(note, case_identifier)
            if not ac_fast_check_current_user_has_case_access(
                note.note_case_id, [CaseAccessLevel.full_access]
            ):
                return ac_api_return_access_denied(caseid=note.note_case_id)

            notes_delete_revision(identifier, revision_number)
            return response_api_deleted()

        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def restore_revision(self, case_identifier, identifier, revision_number):
        try:
            note = notes_get(identifier)
            self._check_note_and_case_identifier_match(note, case_identifier)
            if not ac_fast_check_current_user_has_case_access(
                note.note_case_id, [CaseAccessLevel.full_access]
            ):
                return ac_api_return_access_denied(caseid=note.note_case_id)

            restored = notes_restore_revision(identifier, revision_number)
            return response_api_success(self._schema.dump(restored))

        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())


notes_operations = NotesOperations()
case_notes_blueprint = Blueprint('case_notes',
                                 __name__,
                                 url_prefix='/<int:case_identifier>/notes')


@case_notes_blueprint.get('')
@ac_api_requires()
def list_notes(case_identifier):
    return notes_operations.list(case_identifier)


@case_notes_blueprint.get('/search')
@ac_api_requires()
def search_notes(case_identifier):
    return notes_operations.search(case_identifier)


@case_notes_blueprint.post('')
@ac_api_requires()
def create_note(case_identifier):
    return notes_operations.create(case_identifier)


@case_notes_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_note(case_identifier, identifier):
    return notes_operations.get(case_identifier, identifier)


@case_notes_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_note(case_identifier, identifier):
    return notes_operations.update(case_identifier, identifier)


@case_notes_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_note(case_identifier, identifier):
    return notes_operations.delete(case_identifier, identifier)


# ---- Revisions --------------------------------------------------------------

@case_notes_blueprint.get('/<int:identifier>/revisions')
@ac_api_requires()
def list_note_revisions(case_identifier, identifier):
    return notes_operations.list_revisions(case_identifier, identifier)


@case_notes_blueprint.get('/<int:identifier>/revisions/<int:revision_number>')
@ac_api_requires()
def get_note_revision(case_identifier, identifier, revision_number):
    return notes_operations.get_revision(case_identifier, identifier, revision_number)


@case_notes_blueprint.delete('/<int:identifier>/revisions/<int:revision_number>')
@ac_api_requires()
def delete_note_revision(case_identifier, identifier, revision_number):
    return notes_operations.delete_revision(case_identifier, identifier, revision_number)


@case_notes_blueprint.post('/<int:identifier>/revisions/<int:revision_number>/restore')
@ac_api_requires()
def restore_note_revision(case_identifier, identifier, revision_number):
    return notes_operations.restore_revision(case_identifier, identifier, revision_number)
