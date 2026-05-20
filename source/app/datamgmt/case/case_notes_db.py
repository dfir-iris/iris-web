#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
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

from sqlalchemy import and_
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from flask_sqlalchemy.pagination import Pagination

from app.datamgmt.db_operations import db_create
from app.datamgmt.db_operations import db_delete
from app.db import db
from app.datamgmt.persistence_error import PersistenceError
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import update_notes_state
from app.models.comments import Comments
from app.models.comments import NotesComments
from app.models.models import NoteDirectory
from app.models.models import NoteRevisions
from app.models.models import Notes
from app.models.models import NotesGroup
from app.models.models import NotesGroupLink
from app.models.authorization import User
from app.models.cases import Cases
from app.models.customers import Client
from app.models.pagination_parameters import PaginationParameters
from app.datamgmt.filtering import paginate


def get_note(note_id):
    note = Notes.query.filter(and_(
        Notes.note_id == note_id
    )).first()

    return note


def get_directory(directory_id):
    return NoteDirectory.query.filter(and_(
        NoteDirectory.id == directory_id
    )).first()


def delete_directory(directory: NoteDirectory):
    # Proceed to delete directory, but remove all associated notes and subdirectories recursively
    if directory:
        # Delete all notes in the directory
        for note in directory.notes:
            delete_note(note.note_id, directory.case_id)

        # Delete all subdirectories
        for subdirectory in directory.subdirectories:
            delete_directory(subdirectory)

        db_delete(directory)

        return True

    return False


def get_note_raw(note_id, caseid) -> Notes:
    note = Notes.query.filter(
        Notes.note_case_id == caseid,
        Notes.note_id == note_id
    ).first()
    return note


def delete_note(note_identifier, case_identifier):
    with db.session.begin_nested():
        NotesGroupLink.query.filter(and_(
            NotesGroupLink.note_id == note_identifier,
            NotesGroupLink.case_id == case_identifier
        )).delete()

        com_ids = NotesComments.query.with_entities(
            NotesComments.comment_id
        ).filter(
            NotesComments.comment_note_id == note_identifier
        ).all()

        com_ids = [c.comment_id for c in com_ids]
        NotesComments.query.filter(NotesComments.comment_id.in_(com_ids)).delete()

        NoteRevisions.query.filter(NoteRevisions.note_id == note_identifier).delete()

        Comments.query.filter(Comments.comment_id.in_(com_ids)).delete()

        Notes.query.filter(Notes.note_id == note_identifier).delete()

        update_notes_state(caseid=case_identifier)


def delete_notes_comments_in_case(case_identifier):
    com_ids = NotesComments.query.with_entities(
        NotesComments.comment_id
    ).join(Notes).filter(
        NotesComments.comment_note_id == Notes.note_id,
        Notes.note_case_id == case_identifier
    ).all()

    com_ids = [c.comment_id for c in com_ids]
    NotesComments.query.filter(NotesComments.comment_id.in_(com_ids)).delete()
    Comments.query.filter(Comments.comment_id.in_(com_ids)).delete()


def update_note(note_content, note_title, update_date, user_id, note_id, caseid):
    note = get_note_raw(note_id, caseid=caseid)

    if note:
        note.note_content = note_content
        note.note_title = note_title
        note.note_lastupdate = update_date
        note.note_user = user_id

        db.session.commit()
        return note

    return None


def update_note_revision(user_identifier, note: Notes) -> bool:
    try:
        latest_version = db.session.query(
            NoteRevisions
        ).filter_by(
            note_id=note.note_id
        ).order_by(
            NoteRevisions.revision_number.desc()
        ).first()
        revision_number = 1 if latest_version is None else latest_version.revision_number + 1

        if (revision_number > 1
                and latest_version.note_title == note.note_title and latest_version.note_content == note.note_content):
                return False

        note_version = NoteRevisions(
            note_id=note.note_id,
            revision_number=revision_number,
            note_title=note.note_title,
            note_content=note.note_content,
            note_user=user_identifier,
            revision_timestamp=datetime.utcnow()
        )
        db_create(note_version)

        return True
    except IntegrityError as e:
        raise PersistenceError(e)


def add_note(note_title, creation_date, user_id, caseid, directory_id, note_content=''):
    note = Notes()
    note.note_title = note_title
    note.note_creationdate = note.note_lastupdate = creation_date
    note.note_content = note_content
    note.note_case_id = caseid
    note.note_user = user_id
    note.directory_id = directory_id

    note.custom_attributes = get_default_custom_attributes('note')
    db.session.add(note)

    update_notes_state(caseid=caseid, userid=user_id)
    db.session.commit()

    return note


def get_groups_short(caseid):
    groups_short = NotesGroup.query.with_entities(
        NotesGroup.group_id,
        NotesGroup.group_uuid,
        NotesGroup.group_title
    ).filter(
        NotesGroup.group_case_id == caseid
    ).order_by(
        NotesGroup.group_id
    ).all()

    return groups_short


def get_notes_from_group(caseid, group_id):
    notes = NotesGroupLink.query.with_entities(
        Notes.note_id,
        Notes.note_uuid,
        Notes.note_title,
        User.user,
        Notes.note_lastupdate
    ).filter(
        NotesGroupLink.case_id == caseid,
        NotesGroupLink.group_id == group_id,
    ).join(
        NotesGroupLink.note
    ).join(
        Notes.user
    ).order_by(
        Notes.note_id
    ).all()

    return notes


def get_groups_detail(caseid):
    groups = NotesGroupLink.query.with_entities(
        NotesGroup.group_id,
        NotesGroup.group_uuid,
        NotesGroup.group_title,
        Notes.note_id,
        Notes.note_uuid,
        Notes.note_title,
        User.user,
        Notes.note_lastupdate
    ).filter(
        NotesGroupLink.case_id == caseid,
    ).join(
        NotesGroupLink.note
    ).join(
        NotesGroupLink.note_group
    ).join(
        Notes.user
    ).group_by(
        NotesGroup.group_id,
        Notes.note_id,
        User.user
    ).all()

    return groups


def get_group_details(group_id, caseid):
    group_l = NotesGroup.query.with_entities(
        NotesGroup.group_id,
        NotesGroup.group_uuid,
        NotesGroup.group_title,
        NotesGroup.group_creationdate,
        NotesGroup.group_lastupdate
    ).filter(
        NotesGroup.group_case_id == caseid
    ).filter(
        NotesGroup.group_id == group_id
    ).first()

    group = None
    if group_l:
        group = group_l._asdict()
        group['notes'] = [note._asdict() for note in get_notes_from_group(caseid=caseid, group_id=group_id)]

    return group


def add_note_group(group_title, caseid, userid, creationdate):
    ng = NotesGroup()
    ng.group_title = group_title
    ng.group_case_id = caseid
    ng.group_user = userid
    ng.group_creationdate = creationdate
    ng.group_lastupdate = creationdate

    db.session.add(ng)

    update_notes_state(caseid=caseid, userid=userid)
    db.session.commit()

    if group_title == '':
        ng.group_title = 'New notes group'

    db.session.commit()

    return ng


def delete_note_group(group_id, caseid):
    ngl = NotesGroupLink.query.with_entities(
        NotesGroupLink.note_id
    ).filter(
        NotesGroupLink.group_id == group_id,
        NotesGroupLink.case_id == caseid
    ).all()

    if not ngl:
        group = NotesGroup.query.filter(and_(
            NotesGroup.group_id == group_id,
            NotesGroup.group_case_id == caseid
        )).first()
        if not group:
            return False

        db.session.delete(group)

        update_notes_state(caseid=caseid)
        db.session.commit()
        return True

    to_delete = [row.note_id for row in ngl]

    NotesGroupLink.query.filter(
        NotesGroupLink.group_id == group_id,
        NotesGroupLink.case_id == caseid
    ).delete()

    db.session.commit()

    for nid in to_delete:
        Notes.query.filter(Notes.note_id == nid).delete()

    NotesGroup.query.filter(and_(
        NotesGroup.group_id == group_id,
        NotesGroup.group_case_id == caseid
    )).delete()

    update_notes_state(caseid=caseid)
    db.session.commit()
    return True


def update_note_group(group_title, group_id, caseid):
    ng = NotesGroup.query.filter(and_(
        NotesGroup.group_id == group_id,
        NotesGroup.group_case_id == caseid
    )).first()

    if ng:
        ng.group_title = group_title

        update_notes_state(caseid=caseid)
        db.session.commit()
        return ng

    return None


def find_pattern_in_notes(pattern, caseid):
    notes = Notes.query.filter(
        Notes.note_content.like(pattern),
        Notes.note_case_id == caseid
    ).with_entities(
        Notes.note_id,
        Notes.note_title
    ).all()

    return notes


def get_case_note_comments(note_id):
    return Comments.query.filter(
        NotesComments.comment_note_id == note_id
    ).join(
        NotesComments,
        Comments.comment_id == NotesComments.comment_id
    ).order_by(
        Comments.comment_date.asc()
    ).all()


def add_comment_to_note(note_id, comment_id):
    ec = NotesComments()
    ec.comment_note_id = note_id
    ec.comment_id = comment_id

    db_create(ec)


def get_case_notes_comments_count(notes_list):
    return NotesComments.query.filter(
        NotesComments.comment_note_id.in_(notes_list)
    ).with_entities(
        NotesComments.comment_note_id,
        NotesComments.comment_id
    ).group_by(
        NotesComments.comment_note_id,
        NotesComments.comment_id
    ).all()


def get_case_note_comment(note_id, comment_id):
    return db.session.query(
        Comments.comment_id,
        Comments.comment_text,
        Comments.comment_date,
        Comments.comment_update_date,
        Comments.comment_uuid,
        Comments.comment_user_id,
        Comments.comment_case_id,
        User.name,
        User.user
    ).join(
        NotesComments,
        Comments.comment_id == NotesComments.comment_id
    ).join(
        User,
        User.id == Comments.comment_user_id
    ).filter(
        NotesComments.comment_note_id == note_id,
        NotesComments.comment_id == comment_id
    ).first()


def delete_note_comment(user_identifier, note_id, comment_id):
    comment = Comments.query.filter(
        Comments.comment_id == comment_id,
        Comments.comment_user_id == user_identifier
    ).first()
    if not comment:
        return False, 'You are not allowed to delete this comment'

    NotesComments.query.filter(
        NotesComments.comment_note_id == note_id,
        NotesComments.comment_id == comment_id
    ).delete()

    db_delete(comment)

    return True, 'Comment deleted'


def get_directories_with_note_count(case_id):
    # Fetch all directories for the given case
    directories = NoteDirectory.query.filter_by(case_id=case_id).order_by(
        NoteDirectory.name.asc()
    ).all()

    # Create a list to store the directories with note counts
    directories_with_note_count = []

    # For each directory, fetch the subdirectories, note count, and note titles
    for directory in directories:
        directory_with_note_count = get_directory_with_note_count(directory)
        notes = [{'id': note.note_id, 'title': note.note_title} for note in directory.notes]
        # Order by note title
        notes = sorted(notes, key=lambda note: note['title'])
        directory_with_note_count['notes'] = notes
        directories_with_note_count.append(directory_with_note_count)

    return directories_with_note_count


def paginate_notes_directories(case_id, pagination_parameters: PaginationParameters) -> Pagination:
    query = NoteDirectory.query.filter_by(case_id=case_id)

    return paginate(NoteDirectory, pagination_parameters, query)


def get_directory_with_note_count(directory):
    note_count = Notes.query.filter_by(directory_id=directory.id).count()

    directory_dict = {
        'id': directory.id,
        'name': directory.name,
        'note_count': note_count,
        'subdirectories': []
    }

    if directory.subdirectories:
        for subdirectory in directory.subdirectories:
            directory_dict['subdirectories'].append(get_directory_with_note_count(subdirectory))

    return directory_dict


def search_notes(search_value):
    search_condition = and_()
    notes = Notes.query.filter(
        Notes.note_content.like(f'%{search_value}%'),
        Cases.client_id == Client.client_id,
        search_condition
    ).with_entities(
        Notes.note_id,
        Notes.note_title,
        Cases.name.label('case_name'),
        Client.name.label('client_name'),
        Cases.case_id
    ).join(
        Notes.case
    ).order_by(
        Client.name
    ).all()

    return [row._asdict() for row in notes]


def search_notes_in_case(case_identifier, search_input):
    notes = Notes.query.filter(
        and_(Notes.note_case_id == case_identifier,
             or_(Notes.note_title.ilike(f'%{search_input}%'),
                 Notes.note_content.ilike(f'%{search_input}%')))
    ).all()
    return notes
