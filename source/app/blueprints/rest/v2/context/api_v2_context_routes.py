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

from flask import Blueprint, request
from flask_login import current_user

from app import db, app
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_success
from app.datamgmt.context.context_db import ctx_search_user_cases
from app.models.cases import Cases
from app.models.models import Client

api_v2_context_blueprint = Blueprint('context_api_v2', __name__, url_prefix='/api/v2')


# TODO put this endpoint back once it adheres to the conventions (verb in URL)
#@api_v2_context_blueprint.route('/context/search-cases', methods=['GET'])
@ac_api_requires()
def cases_context_search_v2():
    """
    V2: Search for user cases based on a query parameter (e.g., investigations not closed).
    """
    search = request.args.get('q')
    data = ctx_search_user_cases(search, current_user.id, max_results=100)
    return response_api_success(data=data)


# TODO put this endpoint back once it adheres to the conventions (verb in URL)
#@api_v2_context_blueprint.route('/context/set', methods=['POST'])
@ac_api_requires()
def set_ctx_v2():
    """
    V2: Set the context elements of a user, such as the current case and its display name.
    """

    ctx = request.form.get('ctx')
    ctx_h = request.form.get('ctx_h')

    current_user.ctx_case = ctx
    current_user.ctx_human_case = ctx_h

    db.session.commit()
    _update_user_case_ctx()

    return response_api_success(data={})


def _update_user_case_ctx():
    """
    Retrieve a list of cases for the case selector.
    """
    res = Cases.query.with_entities(
        Cases.name,
        Client.name,
        Cases.case_id,
        Cases.close_date
    ).join(Cases.client).order_by(Cases.open_date).all()

    data = [row for row in res]

    if current_user and current_user.ctx_case:
        is_found = any(row[2] == current_user.ctx_case for row in data)

        if not is_found:
            # Remove invalid case from the user context
            current_user.ctx_case = None
            current_user.ctx_human_case = "Not set"
            db.session.commit()

    app.jinja_env.globals.update({'cases_context_selector': data})
    return data