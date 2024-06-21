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
from flask_login import current_user

from app.datamgmt.context.context_db import ctx_search_user_cases
from app.util import ac_api_requires
from app.util import response_success

context_rest_blueprint = Blueprint('context_rest', __name__)


@context_rest_blueprint.route('/context/search-cases', methods=['GET'])
@ac_api_requires()
def cases_context_search():
    search = request.args.get('q')

    # Get all investigations not closed
    datao = ctx_search_user_cases(search, current_user.id, max_results=100)

    return response_success(data=datao)
