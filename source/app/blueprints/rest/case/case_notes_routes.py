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

import marshmallow
from datetime import datetime
from flask import Blueprint
from flask import request
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy import and_

from app import db
from app import app
from app.blueprints.rest.case_comments import case_comment_update
from app.business.errors import BusinessProcessingError
from app.business.notes import notes_create
from app.business.notes import notes_list_revisions
from app.business.notes import notes_get_revision
from app.business.notes import notes_delete_revision
from app.business.notes import notes_update
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_notes_db import add_comment_to_note
from app.datamgmt.case.case_notes_db import get_directories_with_note_count
from app.datamgmt.case.case_notes_db import get_directory
from app.datamgmt.case.case_notes_db import delete_directory
from app.datamgmt.case.case_notes_db import delete_note
from app.datamgmt.case.case_notes_db import delete_note_comment
from app.datamgmt.case.case_notes_db import get_case_note_comment
from app.datamgmt.case.case_notes_db import get_case_note_comments
from app.datamgmt.case.case_notes_db import get_note
from app.datamgmt.states import get_notes_state
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.models import Notes
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import CaseNoteDirectorySchema
from app.schema.marshables import CaseNoteRevisionSchema
from app.schema.marshables import CaseNoteSchema
from app.schema.marshables import CommentSchema
from app.blueprints.access_controls import ac_requires_case_identifier
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import endpoint_removed
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success

case_notes_rest_blueprint = Blueprint('case_notes_rest', __name__)


@case_notes_rest_blueprint.route('/case/notes/<int:cur_id>', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_note_detail(cur_id, caseid):
    """
    Returns a note and its comments

    ---
    tags:
      - Case Notes

    parameters:
        - name: cur_id
          in: path
          description: Note ID
          type: integer
          required: true
        - name: caseid
          in: path
          description: Case ID
          type: integer
          required: true
    responses:
        200:
            description: Note and its comments
            schema:
                $ref: '#/definitions/CaseNoteSchema'
        400:
            description: Data error
    """
    try:
        note = get_note(cur_id, caseid=caseid)
        if not note:
            return response_error(msg="Invalid note ID")

        note_comments = get_case_note_comments(cur_id)

        note_schema = CaseNoteSchema()
        comments_schema = CommentSchema(many=True)

        note = note_schema.dump(note)
        note['comments'] = comments_schema.dump(note_comments)

        return response_success(data=note)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@case_notes_rest_blueprint.route('/case/notes/delete/<int:cur_id>', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_note_delete(cur_id, caseid):
    call_modules_hook('on_preload_note_delete', data=cur_id, caseid=caseid)

    note = get_note(cur_id, caseid)
    if not note:
        return response_error("Invalid note ID for this case")

    try:

        delete_note(cur_id, caseid)

    except Exception as e:
        return response_error("Unable to remove note", data=e.__traceback__)

    call_modules_hook('on_postload_note_delete', data=cur_id, caseid=caseid)

    track_activity(f"deleted note \"{note.note_title}\"", caseid=caseid)
    return response_success(f"Note deleted {cur_id}")


@case_notes_rest_blueprint.route('/case/notes/update/<int:cur_id>', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_note_save(cur_id, caseid):
    addnote_schema = CaseNoteSchema()

    try:

        note = notes_update(identifier=cur_id, request_json=request.get_json(), case_identifier=caseid)

        return response_success(f"Note ID {cur_id} saved", data=addnote_schema.dump(note))

    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@case_notes_rest_blueprint.route('/case/notes/<int:cur_id>/revisions/list', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_note_list_history(cur_id, caseid):
    note_version_sc = CaseNoteRevisionSchema(many=True)

    try:

        note_version = notes_list_revisions(identifier=cur_id, case_identifier=caseid)

        return response_success("ok", data=note_version_sc.dump(note_version))

    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@case_notes_rest_blueprint.route('/case/notes/<int:cur_id>/revisions/<int:revision_id>', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_note_revision(cur_id, revision_id, caseid):
    note_version_sc = CaseNoteRevisionSchema()

    try:

        note_version = notes_get_revision(identifier=cur_id,
                                          revision_number=revision_id,
                                          case_identifier=caseid)

        return response_success("ok", data=note_version_sc.dump(note_version))

    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@case_notes_rest_blueprint.route('/case/notes/<int:cur_id>/revisions/<int:revision_id>/delete', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_note_revision_delete(cur_id, revision_id, caseid):
    try:

        notes_delete_revision(identifier=cur_id,
                              revision_number=revision_id,
                              case_identifier=caseid)

        return response_success(f"Revision {revision_id} of note {cur_id} deleted")

    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@case_notes_rest_blueprint.route('/case/notes/add', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_note_add(caseid):
    addnote_schema = CaseNoteSchema()

    try:

        note = notes_create(request_json=request.get_json(), case_identifier=caseid)

        return response_success(f"Note ID {note.note_id} created", data=addnote_schema.dump(note))

    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())


@case_notes_rest_blueprint.route('/case/notes/directories/add', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_directory_add(caseid):
    try:

        directory_schema = CaseNoteDirectorySchema()
        request_data = request.get_json()

        if request_data.get('parent_id') is not None:
            directory_schema.verify_parent_id(request_data['parent_id'],
                                              case_id=caseid)

        request_data.pop('id', None)
        request_data['case_id'] = caseid
        new_directory = directory_schema.load(request_data)

        db.session.add(new_directory)
        db.session.commit()

        track_activity(f"added directory \"{new_directory.name}\"", caseid=caseid)
        return response_success('Directory added', data=directory_schema.dump(new_directory))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@case_notes_rest_blueprint.route('/case/notes/directories/update/<dir_id>', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_directory_update(dir_id, caseid):
    try:

        directory = get_directory(dir_id, caseid)
        if not directory:
            return response_error(msg="Invalid directory ID")

        directory_schema = CaseNoteDirectorySchema()
        request_data = request.get_json()

        request_data['case_id'] = caseid
        if request_data.get('parent_id') is not None:
            directory_schema.verify_parent_id(request_data['parent_id'],
                                              case_id=caseid,
                                              current_id=dir_id)

        new_directory = directory_schema.load(request_data, instance=directory, partial=True)

        db.session.commit()

        track_activity(f"modified directory \"{new_directory.name}\"", caseid=caseid)
        return response_success('Directory modified', data=directory_schema.dump(new_directory))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    except Exception as e:
        app.logger.exception(f"Failed to update directory: {e}")
        return response_error(msg="Internal error", status=500)


@case_notes_rest_blueprint.route('/case/notes/directories/delete/<dir_id>', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_directory_delete(dir_id, caseid):
    try:

        directory = get_directory(dir_id, caseid)
        if not directory:
            return response_error(msg="Invalid directory ID")

        # Proceed to delete directory, but remove all associated notes and subdirectories recursively
        has_succeed = delete_directory(directory, caseid)
        if has_succeed:
            track_activity(f"deleted directory \"{directory.name}\"", caseid=caseid)
            return response_success('Directory deleted')

        return response_error('Unable to delete directory')

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@case_notes_rest_blueprint.route('/case/notes/groups/list', methods=['GET'])
@endpoint_removed('Use /case/notes/directories/filter', 'v2.4.0')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_load_notes_groups(caseid):
    pass


@case_notes_rest_blueprint.route('/case/notes/state', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_notes_state(caseid):
    os = get_notes_state(caseid=caseid)
    if os:
        return response_success(data=os)
    return response_error('No notes state for this case.')


@case_notes_rest_blueprint.route('/case/notes/search', methods=['GET', 'POST'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_search_notes(caseid):
    search_input = request.args.get('search_input')

    notes = Notes.query.filter(
        and_(Notes.note_case_id == caseid,
             or_(Notes.note_title.ilike(f'%{search_input}%'),
                 Notes.note_content.ilike(f'%{search_input}%')))
    ).all()

    note_schema = CaseNoteSchema(many=True)
    serialized_notes = note_schema.dump(notes)

    return response_success(data=serialized_notes)


@case_notes_rest_blueprint.route('/case/notes/groups/add', methods=['POST'])
@endpoint_removed('Use /case/notes/directories/add', 'v2.4.0')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_add_notes_groups(caseid):
    pass


@case_notes_rest_blueprint.route('/case/notes/groups/delete/<int:cur_id>', methods=['POST'])
@endpoint_removed('Use /case/notes/directories/delete/<ID>', 'v2.4.0')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_delete_notes_groups(cur_id, caseid):
    pass


@case_notes_rest_blueprint.route('/case/notes/groups/<int:cur_id>', methods=['GET'])
@endpoint_removed('Use /case/notes/directories/<ID>', 'v2.4.0')
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_get_notes_group(cur_id, caseid):
    pass


@case_notes_rest_blueprint.route('/case/notes/directories/filter', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_filter_notes_directories(caseid):
    if not get_case(caseid=caseid):
        return response_error("Invalid case ID")

    directories = get_directories_with_note_count(caseid)

    return response_success("", data=directories)


@case_notes_rest_blueprint.route('/case/notes/groups/update/<int:cur_id>', methods=['POST'])
@endpoint_removed('Use /case/notes/directories/update/<ID>', 'v2.4.0')
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_edit_notes_groups(cur_id, caseid):
    pass


@case_notes_rest_blueprint.route('/case/notes/<int:cur_id>/comments/list', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_note_list(cur_id, caseid):
    note_comments = get_case_note_comments(cur_id)
    if note_comments is None:
        return response_error('Invalid note ID')

    return response_success(data=CommentSchema(many=True).dump(note_comments))


@case_notes_rest_blueprint.route('/case/notes/<int:cur_id>/comments/add', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_note_add(cur_id, caseid):
    try:
        note = get_note(cur_id, caseid=caseid)
        if not note:
            return response_error('Invalid note ID')

        comment_schema = CommentSchema()

        comment = comment_schema.load(request.get_json())
        comment.comment_case_id = caseid
        comment.comment_user_id = current_user.id
        comment.comment_date = datetime.now()
        comment.comment_update_date = datetime.now()
        db.session.add(comment)
        db.session.commit()

        add_comment_to_note(note.note_id, comment.comment_id)

        db.session.commit()

        hook_data = {
            "comment": comment_schema.dump(comment),
            "note": CaseNoteSchema().dump(note)
        }
        call_modules_hook('on_postload_note_commented', data=hook_data, caseid=caseid)

        track_activity("note \"{}\" commented".format(note.note_title), caseid=caseid)
        return response_success("Note commented", data=comment_schema.dump(comment))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages())


@case_notes_rest_blueprint.route('/case/notes/<int:cur_id>/comments/<int:com_id>', methods=['GET'])
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_note_get(cur_id, com_id, caseid):
    comment = get_case_note_comment(cur_id, com_id)
    if not comment:
        return response_error("Invalid comment ID")

    return response_success(data=comment._asdict())


@case_notes_rest_blueprint.route('/case/notes/<int:cur_id>/comments/<int:com_id>/edit', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_note_edit(cur_id, com_id, caseid):
    return case_comment_update(com_id, 'notes', caseid)


@case_notes_rest_blueprint.route('/case/notes/<int:cur_id>/comments/<int:com_id>/delete', methods=['POST'])
@ac_requires_case_identifier(CaseAccessLevel.full_access)
@ac_api_requires()
def case_comment_note_delete(cur_id, com_id, caseid):
    success, msg = delete_note_comment(cur_id, com_id)
    if not success:
        return response_error(msg)

    call_modules_hook('on_postload_note_comment_delete', data=com_id, caseid=caseid)

    track_activity(f"comment {com_id} on note {cur_id} deleted", caseid=caseid)
    return response_success(msg)
