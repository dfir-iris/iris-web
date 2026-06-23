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

from flask import Blueprint
from flask import request

from app.models.authorization import Permissions
from app.blueprints.iris_user import iris_current_user
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.business.search import search_across
from app.business.search import SUPPORTED_SEARCH_TYPES


search_blueprint = Blueprint('search_rest_v2', __name__, url_prefix='/search')


@search_blueprint.get('')
@ac_api_requires(Permissions.search_across_cases)
def search_across_cases():
    # `types` is a comma-separated list (notes,iocs,comments). We accept
    # repeated `?types=notes&types=iocs` form too — Flask's getlist + a
    # split-on-comma normalises both shapes.
    raw_types = request.args.getlist('types') or []
    search_types = []
    for raw in raw_types:
        for piece in raw.split(','):
            piece = piece.strip()
            if piece:
                search_types.append(piece)

    if not search_types:
        return response_api_error(
            f'Missing types. Expected one or more of {SUPPORTED_SEARCH_TYPES}'
        )

    unknown = [t for t in search_types if t not in SUPPORTED_SEARCH_TYPES]
    if unknown:
        return response_api_error(
            f'Unsupported search type(s): {unknown}. Expected one or more of {SUPPORTED_SEARCH_TYPES}'
        )

    search_value = request.args.get('value')
    if not search_value:
        return response_api_error('Missing search value')

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    case_id = request.args.get('case_id', default=None, type=int)

    # `case_ids` accepts either comma-separated `?case_ids=1,2,3` or
    # repeated `?case_ids=1&case_ids=2` — same flexible shape as the
    # `types` param above.
    raw_case_ids = request.args.getlist('case_ids') or []
    case_ids = []
    for raw in raw_case_ids:
        for piece in raw.split(','):
            piece = piece.strip()
            if piece:
                try:
                    case_ids.append(int(piece))
                except ValueError:
                    continue

    result = search_across(
        search_value=search_value,
        search_types=search_types,
        user_id=iris_current_user.id,
        page=page,
        per_page=per_page,
        case_id=case_id,
        case_ids=case_ids or None,
    )

    return response_api_success(data=result)
