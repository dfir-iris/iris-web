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

from flask import Blueprint
from flask import request
from werkzeug import Response

from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.parsing import parse_fields_parameters
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.models.errors import BusinessProcessingError
from app.business.tags import tags_filter
from app.schema.marshables import TagsSchema
from app.blueprints.access_controls import ac_api_requires


class TagsOperations:

    def __init__(self):
        self._schema = TagsSchema()

    def search(self):
        try:

            tag_title = request.args.get('tag_title', None, type=str)
            if tag_title is None:
                tag_title = request.args.get('term', None, type=str)
            tag_namespace = request.args.get('tag_namespace', None, type=str)

            fields = parse_fields_parameters(request)
            pagination_parameters = parse_pagination_parameters(request)

            filtered_tags = tags_filter(tag_title, tag_namespace, pagination_parameters)

            if fields:
                tags_schema = TagsSchema(only=fields)
            else:
                tags_schema = self._schema

            return response_api_paginated(tags_schema, filtered_tags)
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())


tags_blueprint = Blueprint('tags_rest',
                           __name__,
                           url_prefix='/tags')
tags_operations = TagsOperations()


@tags_blueprint.get('')
@ac_api_requires()
def manage_list_tags() -> Response:
    return tags_operations.search()
