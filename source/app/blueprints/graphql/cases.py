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


from graphene_sqlalchemy import SQLAlchemyObjectType
from graphene import List
from graphene.relay import Node
from graphene import Field
from graphene import Mutation
from graphene import NonNull
from graphene import Int
from graphene import Float
from graphene import String

from app.models.cases import Cases
from app.blueprints.graphql.iocs import IOCObject
from app.business.iocs import get_iocs
from app.business.cases import create
from app.business.cases import delete
from app.business.cases import update

class CaseObject(SQLAlchemyObjectType):
    class Meta:
        model = Cases
        interfaces = [Node]

    # TODO add filters
    # TODO do pagination (maybe present it as a relay Connection?)
    iocs = List(IOCObject, description='Get IOCs associated with the case')

    @staticmethod
    def resolve_iocs(root: Cases, info):
        return get_iocs(root.case_id)


class AddCase(Mutation):

    class Arguments:
        name = NonNull(String)
        description = NonNull(String)
        client = NonNull(Int)

    case = Field(CaseObject)

    @staticmethod
    def mutate(root, info, name, description, client):
        request = {
            'case_name': name,
            'case_description': description,
            'case_customer': client,
            'case_soc_id': ''
        }
        case, _ = create(request)
        return AddCase(case=case)


class DeleteCase(Mutation):

    class Arguments:
        case_id = NonNull(Float)

    case = Field(CaseObject)

    @staticmethod
    def mutate(root, info, case_id):
        delete(case_id)


class UpdateCase(Mutation):

    class Arguments:
        case_id = NonNull(Float)

        name = String(required=False, default_value=None)
        soc_id = Int(required=False, default_value=None)
        classification = String(required=False, default_value=None)
        state = String(required=False, default_value=None)
        severity = String(required=False, default_value=None)
        client = String(required=False, default_value=None)
        owner = String(required=False, default_value=None)
        reviewer = String(required=False, default_value=None)
        tags = String(required=False, default_value=None)

    case = Field(CaseObject)

    @staticmethod
    def mutate(root, info, case_id, name, soc_id, classification, state, severity, client, owner, reviewer, tags):
        request = {}
        if name:
            request['case_name'] = name
        case, _ = update(case_id, request)
        return UpdateCase(case=case)
