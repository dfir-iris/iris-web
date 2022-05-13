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

from flask import Blueprint

from app.models.models import EventCategory
from app.util import api_login_required
from app.util import response_error
from app.util import response_success

manage_event_cat_blueprint = Blueprint('manage_event_cat',
                                        __name__,
                                        template_folder='templates')


# CONTENT ------------------------------------------------
@manage_event_cat_blueprint.route('/manage/event-categories/list', methods=['GET'])
@api_login_required
def list_event_categories(caseid):
    lcat= EventCategory.query.with_entities(
        EventCategory.id,
        EventCategory.name
    ).all()

    data = [row._asdict() for row in lcat]

    return response_success("", data=data)


@manage_event_cat_blueprint.route('/manage/event-categories/<int:cur_id>', methods=['GET'])
@api_login_required
def get_event_category(cur_id, caseid):
    lcat = EventCategory.query.with_entities(
        EventCategory.id,
        EventCategory.name
    ).filter(
        EventCategory.id == cur_id
    ).first()

    if not lcat:
        return response_error(f"Event category ID {cur_id} not found")

    data = lcat._asdict()

    return response_success("", data=data)
