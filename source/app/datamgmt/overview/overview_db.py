#!/usr/bin/env python3
#
#  IRIS Source Code
#  DFIR-IRIS Team
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
import datetime
from sqlalchemy import and_

from app.datamgmt.case.case_tasks_db import get_tasks_cases_mapping
from app.datamgmt.manage.manage_cases_db import user_list_cases_view
from app.models import Cases, CaseClassification
from app.models import Client
from app.models.authorization import User
from app.models.cases import CaseState


def get_overview_db(user_id, show_full):
    """
    Get overview data from the database
    """
    condition = and_(Cases.case_id.in_(user_list_cases_view(user_id)))

    if not show_full:
        condition = and_(condition, Cases.close_date == None)

    open_cases = Cases.query.with_entities(
        Cases.case_id,
        Cases.case_uuid,
        Cases.name.label('case_title'),
        Client.name.label('customer_name'),
        Cases.open_date.label('case_open_date'),
        User.name.label('owner'),
        CaseClassification.name.label('classification'),
        CaseState.state_name.label('state')
    ).filter(
       condition
    ).join(
        Cases.owner,
        Cases.client
    ).outerjoin(
        Cases.classification,
        Cases.state
    ).all()

    tasks_map = get_tasks_cases_mapping()
    tmap = {}
    for task in tasks_map:
        if tmap.get(task.task_case_id) is None:
            tmap[task.task_case_id] = {
                'open_tasks': 0,
                'closed_tasks': 0
            }

        if task.task_status_id in [1, 2, 3]:
            tmap[task.task_case_id]['open_tasks'] += 1
        elif task.task_status_id == 4:
            tmap[task.task_case_id]['closed_tasks'] += 1

    open_cases_list = []
    for case in open_cases:
        c_case = case._asdict()
        c_case['case_open_since_days'] = (datetime.date.today() - case.case_open_date).days
        c_case['case_open_date'] = case.case_open_date.strftime('%d-%m-%Y')
        c_case['tasks_status'] = tmap.get(case.case_id)
        open_cases_list.append(c_case)

    return open_cases_list
