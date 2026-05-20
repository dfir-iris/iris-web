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

from flask import Blueprint
from flask import request
from marshmallow import ValidationError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.access_controls import ac_api_return_access_denied
from app.models.errors import ObjectNotFoundError
from app.models.errors import BusinessProcessingError
from app.schema.marshables import CaseNoteDirectorySchema
from app.schema.marshables import SearchCaseNoteDirectorySchema
from app.business.notes_directories import notes_directories_create
from app.business.notes_directories import notes_directories_get
from app.business.notes_directories import notes_directories_update
from app.business.notes_directories import notes_directories_delete
from app.business.cases import cases_exists
from app.business.notes_directories import notes_directories_filter
from app.models.authorization import CaseAccessLevel


class NotesDirectories:

    def __init__(self):
        self._schema = CaseNoteDirectorySchema()
        self._schema_search = SearchCaseNoteDirectorySchema(exclude=('parent_id', 'case_id'))

    @staticmethod
    def _get_note_directory_in_case(identifier, case_identifier):
        directory = notes_directories_get(identifier)
        if directory.case_id != case_identifier:
            raise ObjectNotFoundError()
        return directory

    def _load(self, request_data, **kwargs):
        return self._schema.load(request_data, **kwargs)

    def search(self, case_identifier):
        if not cases_exists(case_identifier):
            return response_api_not_found()
        if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(case_identifier)

        pagination_parameters = parse_pagination_parameters(request, default_order_by='name', default_direction='asc')
        directories = notes_directories_filter(case_identifier, pagination_parameters)
        return response_api_paginated(self._schema_search, directories)

    def create(self, case_identifier):
        if not cases_exists(case_identifier):
            return response_api_not_found()
        if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        request_data = request.get_json()
        request_data.pop('id', None)
        request_data['case_id'] = case_identifier

        try:
            if request_data.get('parent_id') is not None:
                self._schema.verify_parent_id(request_data['parent_id'], case_id=case_identifier)
            directory = self._load(request_data)

            notes_directories_create(directory)

            return response_api_created(self._schema.dump(directory))
        except ValidationError as e:
            return response_api_error('Data error', data=e.normalized_messages())

    def get(self, case_identifier, identifier):
        if not cases_exists(case_identifier):
            return response_api_not_found()
        if not ac_fast_check_current_user_has_case_access(case_identifier,
                                                          [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        try:
            note_directory = self._get_note_directory_in_case(identifier, case_identifier)

            return response_api_success(self._schema.dump(note_directory))
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())

    def update(self, case_identifier, identifier):
        if not cases_exists(case_identifier):
            return response_api_not_found()
        if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        try:
            directory = self._get_note_directory_in_case(identifier, case_identifier)

            request_data = request.get_json()

            if request_data.get('parent_id') is not None:
                self._schema.verify_parent_id(request_data['parent_id'], case_id=case_identifier, current_id=identifier)
            new_directory = self._load(request_data, instance=directory, partial=True)
            notes_directories_update(new_directory)
            return response_api_success(self._schema.dump(new_directory))
        except ValidationError as e:
            return response_api_error('Data error', data=e.normalized_messages())
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error('Data error', data=e.get_data())

    def delete(self, case_identifier, identifier):
        if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        try:
            directory = self._get_note_directory_in_case(identifier, case_identifier)
            notes_directories_delete(directory)
            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()


notes_directories = NotesDirectories()
case_notes_directories_blueprint = Blueprint('case_notes_directories_rest_v2', __name__, url_prefix='/<int:case_identifier>/notes-directories')


@case_notes_directories_blueprint.post('')
@ac_api_requires()
def create_note_directory(case_identifier):
    return notes_directories.create(case_identifier)


@case_notes_directories_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_note_directory(case_identifier, identifier):
    return notes_directories.get(case_identifier, identifier)


@case_notes_directories_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_note_directory(case_identifier, identifier):
    return notes_directories.update(case_identifier, identifier)


@case_notes_directories_blueprint.delete('<int:identifier>')
@ac_api_requires()
def delete_note_directory(case_identifier, identifier):
    return notes_directories.delete(case_identifier, identifier)


@case_notes_directories_blueprint.get('')
@ac_api_requires()
def get_note_directory_filter(case_identifier):
    return notes_directories.search(case_identifier)
