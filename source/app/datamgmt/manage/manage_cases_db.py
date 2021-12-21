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

from datetime import datetime

from sqlalchemy import and_

from app import db
from app.datamgmt.states import delete_case_states
from app.models import Cases, Client, User, UserActivity, CaseReceivedFile, CaseAssets, IocLink, Notes, NotesGroupLink, \
    NotesGroup, CaseTasks, CaseEventsAssets, IocAssetLink, CasesEvent, CaseEventCategory


def list_cases_dict():
    res = Cases.query.with_entities(
        Cases.name.label('case_name'),
        Cases.description.label('case_description'),
        Client.name.label('client_name'),
        Cases.open_date.label('case_open_date'),
        Cases.close_date.label('case_close_date'),
        Cases.soc_id.label('case_soc_id'),
        User.name.label('opened_by'),
        Cases.case_id
    ).join(
        Cases.client,
        Cases.user
    ).order_by(
        Cases.open_date
    )

    data = []
    for row in res:
        row = row._asdict()
        row['case_open_date'] = row['case_open_date'].strftime("%m/%d/%Y")
        row['case_close_date'] = row['case_close_date'].strftime("%m/%d/%Y") if row["case_close_date"] else ""
        data.append(row)

    return data


def close_case(case_id):
    res = Cases.query.filter(
        Cases.case_id == case_id
    ).first()

    if res:
        res.close_date = datetime.utcnow()

        db.session.commit()
        return res

    return None


def reopen_case(case_id):
    res = Cases.query.filter(
        Cases.case_id == case_id
    ).first()

    if res:
        res.close_date = None

        db.session.commit()
        return res

    return None


def get_case_details_rt(case_id):
    if Cases.query.filter(Cases.case_id == case_id).first():
        res = db.session.query(Cases, Client, User).with_entities(
            Cases.name.label('case_name'), Cases.description, Cases.open_date, Cases.close_date,
            Cases.soc_id, Cases.case_id,
            Client.name.label('customer_name'),
            User.name.label('user_name'), User.user
        ).filter(and_(
            Cases.case_id == case_id,
            Cases.user_id == User.id,
            Client.client_id == Cases.client_id
        ))

    else:
        res = None

    return res


def delete_case(case_id):
    if not Cases.query.filter(Cases.case_id == case_id).first():
        return False

    delete_case_states(caseid=case_id)
    UserActivity.query.filter(UserActivity.case_id == case_id).delete()
    CaseReceivedFile.query.filter(CaseReceivedFile.case_id == case_id).delete()
    IocLink.query.filter(IocLink.case_id == case_id).delete()

    da = CaseAssets.query.with_entities(CaseAssets.asset_id).filter(CaseAssets.case_id == case_id).all()
    for asset in da:
        IocAssetLink.query.filter(asset.asset_id == asset.asset_id).delete()

    CaseEventsAssets.query.filter(CaseEventsAssets.case_id == case_id).delete()
    CaseAssets.query.filter(CaseAssets.case_id == case_id).delete()
    NotesGroupLink.query.filter(NotesGroupLink.case_id == case_id).delete()
    NotesGroup.query.filter(NotesGroup.group_case_id == case_id).delete()
    Notes.query.filter(Notes.note_case_id == case_id).delete()
    CaseTasks.query.filter(CaseTasks.task_case_id == case_id).delete()

    da = CasesEvent.query.with_entities(CasesEvent.event_id).filter(CasesEvent.case_id == case_id).all()
    for event in da:
        CaseEventCategory.query.filter(CaseEventCategory.event_id == event.event_id).delete()

    CasesEvent.query.filter(CasesEvent.case_id == case_id).delete()

    Cases.query.filter(Cases.case_id == case_id).delete()
    db.session.commit()

    return True
