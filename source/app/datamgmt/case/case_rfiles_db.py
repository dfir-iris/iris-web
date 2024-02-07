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

import datetime
from flask_login import current_user
from sqlalchemy import and_
from sqlalchemy import desc

from app import db
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import update_evidences_state
from app.models import CaseReceivedFile
from app.models import Comments
from app.models import EvidencesComments
from app.models.authorization import User


def get_rfiles(caseid):
    crf = CaseReceivedFile.query.filter(
        CaseReceivedFile.case_id == caseid
    ).order_by(
        desc(CaseReceivedFile.date_added)
    ).all()

    return crf


def add_rfile(evidence, caseid, user_id):

    evidence.date_added = datetime.datetime.now()
    evidence.case_id = caseid
    evidence.user_id = user_id

    evidence.custom_attributes = get_default_custom_attributes('evidence')

    db.session.add(evidence)

    update_evidences_state(caseid=caseid, userid=user_id)

    db.session.commit()

    return evidence


def get_rfile(rfile_id, caseid):
    return CaseReceivedFile.query.filter(
        CaseReceivedFile.id == rfile_id,
        CaseReceivedFile.case_id == caseid
    ).first()


def update_rfile(evidence, user_id, caseid):

    evidence.user_id = user_id

    update_evidences_state(caseid=caseid, userid=user_id)
    db.session.commit()
    return evidence


def delete_rfile(rfile_id, caseid):
    with db.session.begin_nested():
        com_ids = EvidencesComments.query.with_entities(
            EvidencesComments.comment_id
        ).filter(
            EvidencesComments.comment_evidence_id == rfile_id
        ).all()

        com_ids = [c.comment_id for c in com_ids]
        EvidencesComments.query.filter(EvidencesComments.comment_id.in_(com_ids)).delete()

        Comments.query.filter(Comments.comment_id.in_(com_ids)).delete()

        CaseReceivedFile.query.filter(and_(
            CaseReceivedFile.id == rfile_id,
            CaseReceivedFile.case_id == caseid,
        )).delete()

        update_evidences_state(caseid=caseid)

        db.session.commit()


def get_case_evidence_comments(evidence_id):
    return Comments.query.filter(
        EvidencesComments.comment_evidence_id == evidence_id
    ).join(
        EvidencesComments,
        Comments.comment_id == EvidencesComments.comment_id
    ).order_by(
        Comments.comment_date.asc()
    ).all()


def add_comment_to_evidence(evidence_id, comment_id):
    ec = EvidencesComments()
    ec.comment_evidence_id = evidence_id
    ec.comment_id = comment_id

    db.session.add(ec)
    db.session.commit()


def get_case_evidence_comments_count(evidences_list):
    return EvidencesComments.query.filter(
        EvidencesComments.comment_evidence_id.in_(evidences_list)
    ).with_entities(
        EvidencesComments.comment_evidence_id,
        EvidencesComments.comment_id
    ).group_by(
        EvidencesComments.comment_evidence_id,
        EvidencesComments.comment_id
    ).all()


def get_case_evidence_comment(evidence_id, comment_id):
    return EvidencesComments.query.filter(
        EvidencesComments.comment_evidence_id == evidence_id,
        EvidencesComments.comment_id == comment_id
    ).with_entities(
        Comments.comment_id,
        Comments.comment_text,
        Comments.comment_date,
        Comments.comment_update_date,
        Comments.comment_uuid,
        User.name,
        User.user
    ).join(
        EvidencesComments.comment
    ).join(
        Comments.user
    ).first()


def delete_evidence_comment(evidence_id, comment_id):
    comment = Comments.query.filter(
        Comments.comment_id == comment_id,
        Comments.comment_user_id == current_user.id
    ).first()
    if not comment:
        return False, "You are not allowed to delete this comment"

    EvidencesComments.query.filter(
        EvidencesComments.comment_evidence_id == evidence_id,
        EvidencesComments.comment_id == comment_id
    ).delete()

    db.session.delete(comment)
    db.session.commit()

    return True, "Comment deleted"
