#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

from functools import wraps
from flask_sqlalchemy.pagination import Pagination

from app import app
from app.blueprints.responses import response_error, response

logger = app.logger


def response_api_success(data):
    return response(200, data=data)


def _get_next_page(paginated_elements: Pagination):
    if paginated_elements.has_next:
        next_page = paginated_elements.has_next
    else:
        next_page = None
    return next_page


def response_api_paginated(schema, paginated_elements: Pagination):
    data = schema.dump(paginated_elements.items, many=True)
    next_page = _get_next_page(paginated_elements)

    result = {
        'total': paginated_elements.total,
        'data': data,
        'last_page': paginated_elements.pages,
        'current_page': paginated_elements.page,
        'next_page': next_page
    }

    return response_api_success(result)

def response_api_deleted():
    return response(204)


def response_api_created(data):
    return response(201, data=data)


def response_api_error(message, data=None):
    content = {
        'message': message
    }
    if data:
        content['data'] = data
    return response(400, data=content)


def response_api_not_found():
    return response(404)


def endpoint_deprecated(alternative_verb, alternative_url):
    def inner_wrap(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            result = f(*args, **kwargs)
            logger.warning(f'Endpoint will be deprecated soon. Use {alternative_verb} {alternative_url} instead')
            result.headers['Link'] = f'<{alternative_url}>; rel="alternate"'
            result.headers['Deprecation'] = True
            return result
        return wrap
    return inner_wrap


def endpoint_removed(message, version):
    def inner_wrap(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            return response_error(f"Endpoint deprecated in {version}. {message}.", status=410)
        return wrap
    return inner_wrap
