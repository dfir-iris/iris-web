#!/usr/bin/env python3
#
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
from sqlalchemy import and_
from sqlalchemy import desc

from app.models import Cases
from app.models import Client
from app.models.authorization import CaseAccessLevel
from app.models.authorization import UserCaseEffectiveAccess


def ctx_get_user_cases(user_id, max_results: int = 100):
    uceas = UserCaseEffectiveAccess.query.with_entities(
        Cases.case_id,
        Cases.name,
        Client.name.label('customer_name'),
        Cases.close_date,
        UserCaseEffectiveAccess.access_level
    ).join(
        UserCaseEffectiveAccess.case,
        Cases.client
    ).order_by(
        desc(Cases.case_id)
    ).filter(
        UserCaseEffectiveAccess.user_id == user_id
    ).limit(max_results).all()

    results = []
    for ucea in uceas:
        if ucea.access_level & CaseAccessLevel.deny_all.value == CaseAccessLevel.deny_all.value:
            continue

        row = ucea._asdict()
        if ucea.access_level == CaseAccessLevel.read_only.value:
            row['access'] = '[Read-only]'
        else:
            row['access'] = ''

        results.append(row)

    return results


def ctx_search_user_cases(search, user_id, max_results: int = 100):
    uceas = UserCaseEffectiveAccess.query.with_entities(
        Cases.case_id,
        Cases.name,
        Client.name.label('customer_name'),
        Cases.close_date,
        UserCaseEffectiveAccess.access_level
    ).join(
        UserCaseEffectiveAccess.case,
        Cases.client
    ).order_by(
        desc(Cases.case_id)
    ).filter(and_(
        UserCaseEffectiveAccess.user_id == user_id,
        Cases.name.ilike('%{}%'.format(search))
    )
    ).limit(max_results).all()

    results = []
    for ucea in uceas:
        if ucea.access_level & CaseAccessLevel.deny_all.value == CaseAccessLevel.deny_all.value:
            continue

        row = ucea._asdict()
        if ucea.access_level == CaseAccessLevel.read_only.value:
            row['access'] = '[Read-only]'
        else:
            row['access'] = ''

        results.append(row)

    return results