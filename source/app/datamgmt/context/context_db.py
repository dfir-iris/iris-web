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
from sqlalchemy import desc

from app.models import Cases
from app.models import Client


def ctx_get_user_cases(user_id):
    res = Cases.query.with_entities(
        Cases.name,
        Client.name.label('customer_name'),
        Cases.case_id,
        Cases.close_date)\
        .join(Cases.client)\
        .filter(Cases.close_date == None)\
        .order_by(desc(Cases.case_id))\
        .all()

    datao = [row._asdict() for row in res]

    res = Cases.query.with_entities(
        Cases.name,
        Client.name.label('customer_name'),
        Cases.case_id,
        Cases.close_date)\
        .join(Cases.client)\
        .filter(Cases.close_date != None)\
        .order_by(desc(Cases.case_id))\
        .all()

    datac = [row._asdict() for row in res]

    return datao, datac