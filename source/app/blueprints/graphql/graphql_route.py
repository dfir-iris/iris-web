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
import base64

from functools import wraps

from flask import request
from flask_wtf import FlaskForm
from flask import Blueprint

from graphql_server.flask import GraphQLView
from graphene import ObjectType
from graphene import Schema
from graphene import Float
from graphene import Int
from graphene import Field
from graphene import String

from graphene_sqlalchemy import SQLAlchemyConnectionField

from app.datamgmt.manage.manage_cases_db import build_filter_case_query
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
from app.blueprints.graphql.sliced_result import SlicedResult


class Query(ObjectType):
    """This is the IRIS GraphQL queries documentation!"""

    cases = SQLAlchemyConnectionField(CaseConnection, classificationId=Float(), clientId=Float(), stateId=Int(),
                                      ownerId=Float(), openDate=String(), name=String(), socId=String(),
                                      severityId=Int(), initialDate=String())
    case = Field(CaseObject, case_id=Float(), description='Retrieve a case by its identifier')
    ioc = Field(IOCObject, ioc_id=Float(), description='Retrieve an ioc by its identifier')

    @staticmethod
    def resolve_cases(root, info, **kwargs):
        query = CaseObject.get_query(info)
        total = query.count()
        if kwargs.get("first"):
            first = kwargs.get("first")
        else:
            first = total
        if kwargs.get("after"):
            after = kwargs.get("after")
            decode_after = base64.b64decode(after)
            start = int(decode_after[16:].decode())
            start += 1
        else:
            start = 0
        query_slice = query.slice(start, start + first).all()
        SlicedResult(query_slice, start, total)
        if kwargs.get("classificationId"):
            case_classification_id = kwargs.get("classificationId")
        else:
            case_classification_id = None
        if kwargs.get("clientId"):
            case_client_id = kwargs.get("clientId")
        else:
            case_client_id = None
        if kwargs.get("stateId"):
            case_state_id = kwargs.get("stateId")
        else:
            case_state_id = None
        if kwargs.get("ownerId"):
            case_owner_id = kwargs.get("ownerId")
        else:
            case_owner_id = None
        if kwargs.get("openDate"):
            start_open_date = kwargs.get("openDate")
        else:
            start_open_date = None
        if kwargs.get("name"):
            case_name = kwargs.get("name")
        else:
            case_name = None
        if kwargs.get("socId"):
            case_soc_id = kwargs.get("socId")
        else:
            case_soc_id = None
        if kwargs.get("severityId"):
            case_severity_id = kwargs.get("severityId")
        else:
            case_severity_id = None
        if kwargs.get("initialDate"):
            end_open_date = kwargs.get("initialDate")
        else:
            end_open_date = None
        filtered_cases = build_filter_case_query(current_user_id=1, case_classification_id=case_classification_id,
                                                 case_customer_id=case_client_id, case_state_id=case_state_id,
                                                 case_owner_id=case_owner_id,  start_open_date=start_open_date,
                                                 case_name=case_name, case_soc_id=case_soc_id,
                                                 case_severity_id=case_severity_id, end_open_date=end_open_date)
        return filtered_cases

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