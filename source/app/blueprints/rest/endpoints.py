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
from app import app
from app.business.errors import BusinessProcessingError
from app.util import response

logger = app.logger


def response_api_success(data):
    return response(200, data=data)


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
