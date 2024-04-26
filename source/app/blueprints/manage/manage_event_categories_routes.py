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

from flask import Blueprint, request

from app.datamgmt.manage.manage_case_objs import search_event_category_by_name
from app.models.models import EventCategory
from app.schema.marshables import EventCategorySchema
from app.util import ac_api_requires
from app.util import response_error
from app.util import response_success

manage_event_cat_blueprint = Blueprint('manage_event_cat',
                                       __name__,
                                       template_folder='templates')


# CONTENT ------------------------------------------------
@manage_event_cat_blueprint.route('/manage/event-categories/list', methods=['GET'])
@ac_api_requires()
def list_event_categories():
    lcat= EventCategory.query.with_entities(
        EventCategory.id,
        EventCategory.name
    ).all()

    data = [row._asdict() for row in lcat]

    return response_success("", data=data)


@manage_event_cat_blueprint.route('/manage/event-categories/<int:cur_id>', methods=['GET'])
@ac_api_requires()
def get_event_category(cur_id):
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


@manage_event_cat_blueprint.route('/manage/event-categories/search', methods=['POST'])
@ac_api_requires()
def search_event_category():
    if not request.is_json:
        return response_error("Invalid request")

    event_category = request.json.get('event_category')
    if event_category is None:
        return response_error("Invalid category. Got None")

    exact_match = request.json.get('exact_match', False)

    # Search for event category with a name that contains the specified search term
    event_category = search_event_category_by_name(event_category, exact_match=exact_match)
    if not event_category:
        return response_error("No category found")

    # Serialize the event category and return them in a JSON response
    schema = EventCategorySchema(many=True)
    return response_success("", data=schema.dump(event_category))

