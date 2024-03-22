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
from flask import request
from flask_wtf import FlaskForm
from flask import Blueprint
from flask_login import current_user

from graphql_server.flask import GraphQLView
from graphene import ObjectType
from graphene import Schema
from graphene import List

from app.util import is_user_authenticated
from app.util import response_error
from app.datamgmt.manage.manage_cases_db import get_filtered_cases
from app.blueprints.graphql.cases import CaseObject


class Query(ObjectType):
    """This is the IRIS GraphQL queries documentation!"""

    # starting with the conversion of '/manage/cases/filter'
    cases = List(CaseObject, description='Retrieves cases')

    def resolve_cases(root, info):
        # TODO add all parameters to filter
        return get_filtered_cases(current_user.id)


def _check_authentication_wrapper(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if request.method == 'POST':
            cookie_session = request.cookies.get('session')
            if cookie_session:
                form = FlaskForm()
                if not form.validate():
                    return response_error('Invalid CSRF token')
                elif request.is_json:
                    request.json.pop('csrf_token')

        if not is_user_authenticated(request):
            return response_error('Authentication required', status=401)

        return f(*args, **kwargs)
    return wrap


def _create_blueprint():
    schema = Schema(query=Query)
    graphql_view = GraphQLView.as_view('graphql', schema=schema)
    graphql_view_with_authentication = _check_authentication_wrapper(graphql_view)

    blueprint = Blueprint('graphql', __name__)
    blueprint.add_url_rule('/graphql', view_func=graphql_view_with_authentication, methods=['POST'])

    return blueprint


graphql_blueprint = _create_blueprint()

# TODO I am unsure about the code organization (directories)
