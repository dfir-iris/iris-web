#  IRIS Source Code
#  Copyright (C) ${current_year} - DFIR-IRIS
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
from graphql_server.flask import GraphQLView
from graphene import ObjectType, String, Schema

from app.util import is_user_authenticated
from app.util import response_error


class Query(ObjectType):
    """Query documentation"""

    hello = String(first_name=String(default_value='stranger'), description='Field documentation')
    goodbye = String()

    def resolve_hello(root, info, first_name):
        return f'Hello {first_name}!'

    def resolve_goodbye(root, info):
        return 'See ya!'


# util.ac_api_requires does not seem to work => it leads to error:
#   TypeError: dispatch_request() got an unexpected keyword argument 'caseid'
# so I rewrote a simpler decorator...
# Maybe, no decorator is needed (since graphql needs only one endpoint) => try to write code directly
def ac_graphql_requires():
    def inner_wrap(f):
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
    return inner_wrap


schema = Schema(query=Query)
graphql_view = GraphQLView.as_view('graphql', schema=schema)

graphql_blueprint = Blueprint('graphql', __name__)


@graphql_blueprint.route('/graphql', methods=['POST'])
@ac_graphql_requires()
def process_graphql_request(*args, **kwargs):
    return graphql_view(*args, **kwargs)

# TODO add first unit tests: test request is rejected with wrong token, test request is successful
# TODO try to rewrite this as another blueprint and group it with the other blueprints
# TODO how to handle permissions?
# TODO link with the database: graphene-sqlalchemy
# TODO I am unsure about the code organization (directories)
# curl --insecure -X POST -H "Content-Type: application/json" -d '{ "query": "{ hello(firstName: \"friendly\") }" }' https://127.0.0.1/graphql
#app.add_url_rule('/graphql', view_func=GraphQLView.as_view('graphql', schema=schema))
#API_KEY=B8BA5D730210B50F41C06941582D7965D57319D5685440587F98DFDC45A01594
#curl --insecure -X POST --header 'Authorization: Bearer '${API_KEY} --header 'Content-Type: application/json' -d '{ "query": "{ hello(firstName: \"friendly\") }" }' https://127.0.0.1/graphql
