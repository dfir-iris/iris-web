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

import datetime
from sqlalchemy import and_
from sqlalchemy import desc

from app import db
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.states import update_evidences_state
from app.models import CaseReceivedFile
from app.models.authorization import User


def get_rfiles(caseid):
    crf = CaseReceivedFile.query.with_entities(
        CaseReceivedFile.id,
        CaseReceivedFile.filename,
        CaseReceivedFile.date_added,
        CaseReceivedFile.file_hash,
        CaseReceivedFile.file_description,
        CaseReceivedFile.file_size,
        User.name.label('username')
    ).filter(
        CaseReceivedFile.case_id == caseid
    ).join(CaseReceivedFile.user).order_by(desc(CaseReceivedFile.date_added)).all()

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
    CaseReceivedFile.query.filter(and_(
        CaseReceivedFile.id == rfile_id,
        CaseReceivedFile.case_id == caseid,
    )).delete()

    update_evidences_state(caseid=caseid)

    db.session.commit()
