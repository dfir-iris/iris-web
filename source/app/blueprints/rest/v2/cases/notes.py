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

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.access_controls import ac_api_return_access_denied
from app.schema.marshables import CaseNoteSchema
from app.models.authorization import CaseAccessLevel
from app.models.models import Notes
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.business.notes import notes_create
from app.business.notes import notes_get
from app.business.cases import cases_exists
from app.business.errors import BusinessProcessingError
from app.business.errors import ObjectNotFoundError


case_notes_blueprint = Blueprint('case_notes',
                                 __name__,
                                 url_prefix='/<int:case_identifier>/notes')


@case_notes_blueprint.post('')
@ac_api_requires()
def create_note(case_identifier):
    if not cases_exists(case_identifier):
        return response_api_not_found()

    if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(caseid=case_identifier)

    note_schema = CaseNoteSchema()
    try:
        note = notes_create(request_json=request.get_json(), case_identifier=case_identifier)

        return response_api_created(note_schema.dump(note))

    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())


@case_notes_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_note(case_identifier, identifier):

    note_schema = CaseNoteSchema()

    try:
        note = notes_get(identifier)
        _check_note_and_case_identifier_match(note, case_identifier)

        if not ac_fast_check_current_user_has_case_access(note.note_case_id, [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=note.note_case_id)

        return response_api_success(note_schema.dump(note))
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())


def _check_note_and_case_identifier_match(note: Notes, case_identifier):
    if note.note_case_id != case_identifier:
        raise ObjectNotFoundError
