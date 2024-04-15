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

from graphql_server.flask import GraphQLView
from graphene_sqlalchemy import SQLAlchemyConnectionField
from graphene import ObjectType
from graphene import Schema
from graphene import Float
from graphene import Field
from graphene import String
from graphene import Int

from app.util import is_user_authenticated
from app.util import response_error

from app.blueprints.graphql.cases import CaseObject
from app.blueprints.graphql.iocs import IOCObject
from app.blueprints.graphql.iocs import IOCCreate
from app.blueprints.graphql.iocs import IOCUpdate
from app.blueprints.graphql.iocs import IOCDelete
from app.business.cases import get_case_by_identifier
from app.business.iocs import get_ioc_by_identifier
from app.blueprints.graphql.cases import CaseCreate
from app.blueprints.graphql.cases import CaseDelete
from app.blueprints.graphql.cases import CaseUpdate
from app.blueprints.graphql.cases import CaseConnection


class Query(ObjectType):
    """This is the IRIS GraphQL queries documentation!"""

    # starting with the conversion of '/manage/cases/filter'
    cases = SQLAlchemyConnectionField(CaseConnection, name=String(), clientId=Float(), classificationId=Int(), stateId=Int(), ownerId=Float(), openDate=String(), initialDate=String(), caseId=Float(), severityId=Int(), socId=String(), closeDate=String())
    case = Field(CaseObject, case_id=Float(), description='Retrieve a case by its identifier')
    ioc = Field(IOCObject, ioc_id=Float(), description='Retrieve an ioc by its identifier')

    @staticmethod
    def resolve_cases(root, info, **kwargs):
        query = CaseObject.get_query(info)
        if kwargs.get('name'):
            query = query.filter_by(name=kwargs['name'])
        if kwargs.get('clientId'):
            query = query.filter_by(client_id=kwargs['clientId'])
        if kwargs.get('classificationId'):
            query = query.filter_by(classification_id=kwargs['classificationId'])
        if kwargs.get('stateId'):
            query = query.filter_by(state_id=kwargs['stateId'])
        if kwargs.get('ownerId'):
            query = query.filter_by(owner_id=kwargs['ownerId'])
        if kwargs.get('openDate'):
            query = query.filter_by(open_date=kwargs['openDate'])
        if kwargs.get('initialDate'):
            query = query.filter_by(initial_date=kwargs['initialDate'])
        if kwargs.get('caseId'):
            query = query.filter_by(case_id=kwargs['caseId'])
        if kwargs.get('socId'):
            query = query.filter_by(soc_id=kwargs['socId'])
        if kwargs.get('severityId'):
            query = query.filter_by(severity_id=kwargs['severityId'])
        if kwargs.get('closeDate'):
            query = query.filter_by(close_date=kwargs['closeDate'])
        return query

    @staticmethod
    def resolve_case(root, info, case_id):
        return get_case_by_identifier(case_id)

    @staticmethod
    def resolve_ioc(root, info, ioc_id):
        return get_ioc_by_identifier(ioc_id)


class Mutation(ObjectType):

    ioc_create = IOCCreate.Field()
    ioc_update = IOCUpdate.Field()
    ioc_delete = IOCDelete.Field()

    case_create = CaseCreate.Field()
    case_delete = CaseDelete.Field()
    case_update = CaseUpdate.Field()


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
    schema = Schema(query=Query, mutation=Mutation)
    graphql_view = GraphQLView.as_view('graphql', schema=schema)
    graphql_view_with_authentication = _check_authentication_wrapper(graphql_view)

    blueprint = Blueprint('graphql', __name__)
    blueprint.add_url_rule('/graphql', view_func=graphql_view_with_authentication, methods=['POST'])

    return blueprint


graphql_blueprint = _create_blueprint()