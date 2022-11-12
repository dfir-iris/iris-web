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

import binascii
from sqlalchemy import and_

from app import db
from app.models import Tags
from app.models.cases import CaseProtagonist
from app.models.cases import CaseTags
from app.models.cases import Cases
from app.models.models import CaseTemplateReport
from app.models.models import Client
from app.models.models import Languages
from app.models.models import ReportType
from app.models.authorization import User


def get_case_summary(caseid):
    case_summary = Cases.query.filter(
        Cases.case_id == caseid
    ).with_entities(
        Cases.name.label('case_name'),
        Cases.open_date.label('case_open'),
        User.name.label('user'),
        Client.name.label('customer')
    ).join(
        Cases.user, Cases.client
    ).first()

    return case_summary


def get_case(caseid):
    return Cases.query.filter(Cases.case_id == caseid).first()


def case_exists(caseid):
    return Cases.query.filter(Cases.case_id == caseid).count()


def get_case_client_id(caseid):
    client_id = Cases.query.with_entities(
        Client.client_id
    ).filter(
        Cases.case_id == caseid
    ).join(Cases.client).first()

    return client_id.client_id


def case_get_desc(caseid):
    case_desc = Cases.query.with_entities(
        Cases.description
    ).filter(
        Cases.case_id == caseid
    ).first()

    return case_desc


def case_get_desc_crc(caseid):
    partial_case = case_get_desc(caseid)

    if partial_case:
        desc = partial_case.description
        if not desc:
            desc = ""
        desc_crc32 = binascii.crc32(desc.encode('utf-8'))
    else:
        desc = None
        desc_crc32 = None

    return desc_crc32, desc


def case_set_desc_crc(desc, caseid):
    lcase = get_case(caseid)

    if lcase:
        if not desc:
            desc = ""
        lcase.description = desc
        db.session.commit()
        return True

    return False


def get_case_report_template():
    reports = CaseTemplateReport.query.with_entities(
        CaseTemplateReport.id,
        CaseTemplateReport.name,
        Languages.name,
        CaseTemplateReport.description
    ).join(
        CaseTemplateReport.language,
        CaseTemplateReport.report_type
    ).filter(
        ReportType.name == "Investigation"
    ).all()

    return reports


def save_case_tags(tags, case_id):
    case = get_case(case_id)
    to_add = []

    existing_tags = CaseTags.query.filter(
        CaseTags.case_id == case_id
    ).all()
    existing_tags = [tag.tag_id for tag in existing_tags]

    for tag in tags.split(','):
        tag = tag.strip()
        if tag:
            tg = Tags.query.filter(Tags.tag_title == tag).first()
            if not tg:
                tg = Tags()
                tg.tag_title = tag
                tg.tag_creation_date = datetime.datetime.now()
                db.session.add(tg)
                db.session.commit()
            to_add.append(tg.id)

    CaseTags.query.filter(and_(
        CaseTags.case_id == case_id,
        CaseTags.tag_id.notin_(to_add)
    )).delete()

    to_delete = [tag for tag in existing_tags if tag not in to_add]
    if to_delete:
        Tags.query.filter(Tags.id.in_(to_delete)).delete()

    for tag in to_add:
        if tag not in existing_tags:
            ct = CaseTags()
            ct.case_id = case_id
            ct.tag_id = tag
            db.session.add(ct)

    db.session.commit()


def get_case_tags(case_id):
    tags = CaseTags.query.with_entities(
        Tags.tag_title
    ).filter(
        CaseTags.case_id == case_id
    ).join(
        CaseTags.tag
    ).all()

    return [tag.tag_title for tag in tags]


def get_activities_report_template():
    reports = CaseTemplateReport.query.with_entities(
        CaseTemplateReport.id,
        CaseTemplateReport.name,
        Languages.name,
        CaseTemplateReport.description
    ).join(
        CaseTemplateReport.language,
        CaseTemplateReport.report_type
    ).filter(
        ReportType.name == "Activities"
    ).all()

    return reports


def case_name_exists(case_name, client_name):
    res = Cases.query.with_entities(
        Cases.name, Client.name
    ).filter(and_(
        Cases.name == case_name,
        Client.name == client_name
    )).join(
        Cases.client
    ).first()

    return True if res else False


def register_case_protagonists(case_id, protagonists):

    CaseProtagonist.query.filter(
        CaseProtagonist.case_id == case_id
    ).delete()

    for protagonist in protagonists:
        for key in ['role', 'name']:
            if not protagonist.get(key):
                continue

        cp = CaseProtagonist()
        cp.case_id = case_id
        cp.role = protagonist.get('role')
        cp.name = protagonist.get('name')
        cp.contact = protagonist.get('contact')
        db.session.add(cp)

    db.session.commit()
