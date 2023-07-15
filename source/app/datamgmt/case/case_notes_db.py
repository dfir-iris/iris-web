#!/usr/bin/env python3
#
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
from flask_login import current_user
from sqlalchemy import and_

from app import db
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import update_notes_state
from app.models import Comments
from app.models import Notes
from app.models import NotesComments
from app.models import NotesGroup
from app.models import NotesGroupLink
from app.models.authorization import User


def get_note(note_id, caseid=None):
    note = Notes.query.with_entities(
        Notes.note_id,
        Notes.note_uuid,
        Notes.note_title,
        Notes.note_content,
        Notes.note_creationdate,
        Notes.note_lastupdate,
        NotesGroupLink.group_id,
        NotesGroup.group_title,
        NotesGroup.group_uuid,
        Notes.custom_attributes,
        Notes.note_case_id
    ).filter(and_(
        Notes.note_id == note_id,
        Notes.note_case_id == caseid
    )).join(
        NotesGroupLink.note,
        NotesGroupLink.note_group
    ).first()

    return note


def get_note_raw(note_id, caseid):
    note = Notes.query.filter(
        Notes.note_case_id == caseid,
        Notes.note_id == note_id
    ).first()
    return note


def delete_note(note_id, caseid):
    with db.session.begin_nested():
        NotesGroupLink.query.filter(and_(
            NotesGroupLink.note_id == note_id,
            NotesGroupLink.case_id == caseid
        )).delete()

        com_ids = NotesComments.query.with_entities(
            NotesComments.comment_id
        ).filter(
            NotesComments.comment_note_id == note_id
        ).all()

        com_ids = [c.comment_id for c in com_ids]
        NotesComments.query.filter(NotesComments.comment_id.in_(com_ids)).delete()

        Comments.query.filter(Comments.comment_id.in_(com_ids)).delete()

        Notes.query.filter(Notes.note_id == note_id).delete()

        update_notes_state(caseid=caseid)


def update_note(note_content, note_title, update_date, user_id, note_id, caseid):
    note = get_note_raw(note_id, caseid=caseid)

    if note:
        note.note_content = note_content
        note.note_title = note_title
        note.note_lastupdate = update_date
        note.note_user = user_id

        db.session.commit()
        return note

    else:
        return None


def add_note(note_title, creation_date, user_id, caseid, group_id, note_content=""):
    note = Notes()
    note.note_title = note_title
    note.note_creationdate = note.note_lastupdate = creation_date
    note.note_content = note_content
    note.note_case_id = caseid
    note.note_user = user_id

    note.custom_attributes = get_default_custom_attributes('note')
    db.session.add(note)

    update_notes_state(caseid=caseid, userid=user_id)
    db.session.commit()

    if note.note_id:
        ngl = NotesGroupLink()
        ngl.note_id = note.note_id
        ngl.group_id = group_id
        ngl.case_id = caseid

        db.session.add(ngl)
        db.session.commit()

        return note

    else:
        return None


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
        NotesGroupLink.note,
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
        NotesGroupLink.note,
        NotesGroupLink.note_group,
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
        ng.group_title = "New notes group"

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

    else:
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

    db.session.add(ec)
    db.session.commit()


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
    return NotesComments.query.filter(
        NotesComments.comment_note_id == note_id,
        NotesComments.comment_id == comment_id
    ).with_entities(
        Comments.comment_id,
        Comments.comment_text,
        Comments.comment_date,
        Comments.comment_update_date,
        Comments.comment_uuid,
        User.name,
        User.user
    ).join(
        NotesComments.comment,
        Comments.user
    ).first()


def delete_note_comment(note_id, comment_id):
    comment = Comments.query.filter(
        Comments.comment_id == comment_id,
        Comments.comment_user_id == current_user.id
    ).first()
    if not comment:
        return False, "You are not allowed to delete this comment"

    NotesComments.query.filter(
        NotesComments.comment_note_id == note_id,
        NotesComments.comment_id == comment_id
    ).delete()

    db.session.delete(comment)
    db.session.commit()

    return True, "Comment deleted"
