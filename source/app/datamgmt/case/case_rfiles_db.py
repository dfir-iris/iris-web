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
from sqlalchemy import desc
from flask_sqlalchemy.pagination import Pagination

from app.datamgmt.db_operations import db_create
from app.datamgmt.db_operations import db_delete
from app.db import db
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import update_evidences_state
from app.models.evidences import CaseReceivedFile
from app.models.comments import Comments
from app.models.comments import EvidencesComments
from app.models.authorization import User
from app.models.pagination_parameters import PaginationParameters
from app.datamgmt.filtering import paginate


def get_rfiles(caseid):
    crf = CaseReceivedFile.query.filter(
        CaseReceivedFile.case_id == caseid
    ).order_by(
        desc(CaseReceivedFile.date_added)
    ).all()

    return crf


def get_paginated_evidences(case_identifier, pagination_parameters: PaginationParameters) -> Pagination:
    query = CaseReceivedFile.query.filter(
        CaseReceivedFile.case_id == case_identifier
    )

    return paginate(CaseReceivedFile, pagination_parameters, query)


def add_rfile(evidence: CaseReceivedFile, caseid, user_id):

    evidence.date_added = datetime.datetime.now()
    evidence.case_id = caseid
    evidence.user_id = user_id

    evidence.custom_attributes = get_default_custom_attributes('evidence')

    db.session.add(evidence)

    update_evidences_state(caseid=caseid, userid=user_id)

    db.session.commit()

    return evidence


def get_rfile(rfile_id):
    return CaseReceivedFile.query.filter(CaseReceivedFile.id == rfile_id).first()


def update_rfile(evidence, user_id, caseid):

    evidence.user_id = user_id

    update_evidences_state(caseid=caseid, userid=user_id)
    db.session.commit()
    return evidence


def delete_rfile(evidence: CaseReceivedFile):
    with db.session.begin_nested():
        com_ids = EvidencesComments.query.with_entities(
            EvidencesComments.comment_id
        ).filter(
            EvidencesComments.comment_evidence_id == evidence.id
        ).all()

        com_ids = [c.comment_id for c in com_ids]
        EvidencesComments.query.filter(EvidencesComments.comment_id.in_(com_ids)).delete()

        Comments.query.filter(Comments.comment_id.in_(com_ids)).delete()

        db.session.delete(evidence)

        update_evidences_state(caseid=evidence.case_id)

        db.session.commit()


def delete_evidences_comments_in_case(case_identifier):
    com_ids = EvidencesComments.query.with_entities(
        EvidencesComments.comment_id
    ).join(CaseReceivedFile).filter(
        EvidencesComments.comment_evidence_id == CaseReceivedFile.id,
        CaseReceivedFile.case_id == case_identifier
    ).all()

    com_ids = [c.comment_id for c in com_ids]
    EvidencesComments.query.filter(EvidencesComments.comment_id.in_(com_ids)).delete()
    Comments.query.filter(Comments.comment_id.in_(com_ids)).delete()


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

    db_create(ec)


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
        Comments.comment_user_id,
        Comments.comment_case_id,
        User.name,
        User.user
    ).join(
        EvidencesComments.comment
    ).join(
        Comments.user
    ).first()


def delete_evidence_comment(user_identifier, evidence_id, comment_id):
    comment = Comments.query.filter(
        Comments.comment_id == comment_id,
        Comments.comment_user_id == user_identifier
    ).first()
    if not comment:
        return False, "You are not allowed to delete this comment"

    EvidencesComments.query.filter(
        EvidencesComments.comment_evidence_id == evidence_id,
        EvidencesComments.comment_id == comment_id
    ).delete()

    db_delete(comment)

    return True, "Comment deleted"
