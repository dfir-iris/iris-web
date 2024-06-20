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
from app.models import Cases
from app.schema.marshables import CaseDetailsSchema


def get_overview_db(user_id, show_full):
    """
    Get overview data from the database
    """
    condition = and_(Cases.case_id.in_(user_list_cases_view(user_id)))

    if not show_full:
        condition = and_(condition, Cases.close_date == None)

    open_cases = Cases.query.filter(
       condition
    ).join(
        Cases.owner
    ).join(
        Cases.client
    ).all()

    cases_list = []
    tasks_map = get_tasks_cases_mapping(open_cases_only=not show_full)
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

    # open_cases_list = []
    for case in open_cases:
        c_case = CaseDetailsSchema().dump(case)
        c_case['case_open_since_days'] = (datetime.date.today() - case.open_date).days
        c_case['tasks_status'] = tmap.get(case.case_id)
        cases_list.append(c_case)

    return cases_list
