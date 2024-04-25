#  IRIS Source Code
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

from sqlalchemy import and_, case, or_, asc
from sqlalchemy import desc

from app.models import Cases
from app.models import Client
from app.models.authorization import CaseAccessLevel
from app.models.authorization import UserCaseEffectiveAccess
from app.datamgmt.authorization import has_deny_all_access_level


def ctx_get_user_cases(user_id, max_results: int = 100):
    user_priority_sort = case(
        [(Cases.owner_id == user_id, 0)],
        else_=1
    )
    uceas = UserCaseEffectiveAccess.query.with_entities(
        Cases.case_id,
        Cases.name,
        Client.name.label('customer_name'),
        Cases.close_date,
        Cases.owner_id,
        UserCaseEffectiveAccess.access_level
    ).join(
        UserCaseEffectiveAccess.case
    ).join(
        Cases.client
    ).order_by(
        asc(user_priority_sort),
        desc(Cases.case_id)
    ).filter(
        UserCaseEffectiveAccess.user_id == user_id
    ).limit(max_results).all()

    results = []
    for ucea in uceas:
        if has_deny_all_access_level(ucea):
            continue

        row = ucea._asdict()
        if ucea.access_level == CaseAccessLevel.read_only.value:
            row['access'] = '[Read-only]'
        else:
            row['access'] = ''

        results.append(row)

    return results


def ctx_search_user_cases(search, user_id, max_results: int = 100):
    user_priority_sort = case(
        (Cases.owner_id == user_id, 0),
        else_=1
    ).label("user_priority")

    conditions = []
    if not search:
        conditions.append(UserCaseEffectiveAccess.user_id == user_id)

    else:
        conditions.append(and_(
            UserCaseEffectiveAccess.user_id == user_id,
            or_(
                Cases.name.ilike('%{}%'.format(search)),
                Client.name.ilike('%{}%'.format(search))
        )))

    uceas = UserCaseEffectiveAccess.query.with_entities(
        Cases.case_id,
        Cases.name,
        Cases.owner_id,
        Client.name.label('customer_name'),
        Cases.close_date,
        UserCaseEffectiveAccess.access_level
    ).join(
        UserCaseEffectiveAccess.case
    ).join(
        Cases.client
    ).order_by(
        user_priority_sort,
        desc(Cases.case_id)
    ).filter(
        *conditions
    ).limit(max_results).all()


    results = []
    for ucea in uceas:
        if has_deny_all_access_level(ucea):
            continue

        row = ucea._asdict()
        if ucea.access_level == CaseAccessLevel.read_only.value:
            row['access'] = '[Read-only]'
        else:
            row['access'] = ''

        results.append(row)

    return results
