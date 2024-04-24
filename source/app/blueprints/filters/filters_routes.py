#  IRIS Source Code
#  Copyright (C) 2023 - DFIR-IRIS
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
from flask import Blueprint, request
from flask_login import current_user
from werkzeug import Response

from app import db
from app.datamgmt.filters.filters_db import get_filter_by_id
from app.datamgmt.filters.filters_db import list_filters_by_type
from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import SavedFilterSchema
from app.util import ac_api_requires
from app.util import response_success
from app.util import response_error

saved_filters_blueprint = Blueprint('saved_filters', __name__,
                                    template_folder='templates')


@saved_filters_blueprint.route('/filters/add', methods=['POST'])
@ac_api_requires()
def filters_add_route() -> Response:
    """
    Add a new saved filter

    args:
        None

    returns:
        The new saved filter
    """
    saved_filter_schema = SavedFilterSchema()

    try:
        # Load the JSON data from the request
        data = request.get_json()
        data['created_by'] = current_user.id

        new_saved_filter = saved_filter_schema.load(data)

        db.session.add(new_saved_filter)
        db.session.commit()

        track_activity(f'Search filter added', ctx_less=True)

        return response_success(data=saved_filter_schema.dump(new_saved_filter))

    except Exception as e:
        # Handle any errors during deserialization or DB operations
        return response_error(str(e))


@saved_filters_blueprint.route('/filters/update/<int:filter_id>', methods=['POST'])
@ac_api_requires()
def filters_update_route(filter_id) -> Response:
    """
    Update a saved filter

    args:
        filter_id: The ID of the saved filter to update

    returns:
        The updated saved filter
    """
    saved_filter_schema = SavedFilterSchema()

    try:
        data = request.get_json()

        saved_filter = get_filter_by_id(filter_id)
        if not saved_filter:
            return response_error('Filter not found')

        saved_filter_schema.load(data, instance=saved_filter, partial=True)
        db.session.commit()

        track_activity(f'Search filter {filter_id} updated', ctx_less=True)

        return response_success(data=saved_filter_schema.dump(saved_filter))

    except Exception as e:
        # Handle any errors during deserialization or DB operations
        return response_error(str(e))


@saved_filters_blueprint.route('/filters/delete/<int:filter_id>', methods=['POST'])
@ac_api_requires()
def filters_delete_route(filter_id) -> Response:
    """
    Delete a saved filter

    args:
        filter_id: The ID of the saved filter to delete

    returns:
        Response object
    """
    try:
        saved_filter = get_filter_by_id(filter_id)
        if not saved_filter:
            return response_error('Filter not found')

        db.session.delete(saved_filter)
        db.session.commit()

        track_activity(f'Search filter {filter_id} deleted', ctx_less=True)

        return response_success()

    except Exception as e:
        # Handle any errors during DB operations
        return response_error(str(e))


@saved_filters_blueprint.route('/filters/<int:filter_id>', methods=['GET'])
@ac_api_requires()
def filters_get_route(filter_id) -> Response:
    """
    Get a saved filter

    args:
        filter_id: The ID of the saved filter to get

    returns:
        Response object
    """
    saved_filter_schema = SavedFilterSchema()

    try:
        saved_filter = get_filter_by_id(filter_id)
        if not saved_filter:
            return response_error('Filter not found')

        return response_success(data=saved_filter_schema.dump(saved_filter))

    except Exception as e:
        # Handle any errors during DB operations
        return response_error(str(e))


@saved_filters_blueprint.route('/filters/<string:filter_type>/list', methods=['GET'])
@ac_api_requires()
def filters_list_route(filter_type) -> Response:
    """
    List saved filters

    args:
        filter_type: The type of filter to list (e.g. 'search')


    returns:
        Response object
    """
    saved_filter_schema = SavedFilterSchema(many=True)

    try:
        saved_filters = list_filters_by_type(str(filter_type).lower())

        return response_success(data=saved_filter_schema.dump(saved_filters))

    except Exception as e:
        # Handle any errors during DB operations
        return response_error(str(e))
