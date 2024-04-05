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


class CaseCreate(Mutation):

    class Arguments:
        name = NonNull(String)
        description = NonNull(String)
        client = NonNull(Int)

        soc_id = String()
        classification_id = String()

    case = Field(CaseObject)

    @staticmethod
    def mutate(root, info, name, description, client, soc_id=None, classification_id=None):
        request = {
            'case_name': name,
            'case_description': description,
            'case_customer': client,
            'case_soc_id': ''
        }
        if soc_id:
            request['case_soc_id'] = soc_id
        if classification_id:
            request['classification_id'] = classification_id
        case, _ = create(request)
        return CaseCreate(case=case)


class CaseDelete(Mutation):

    class Arguments:
        case_id = NonNull(Float)

    case = Field(CaseObject)

    @staticmethod
    def mutate(root, info, case_id):
        delete(case_id)


class CaseUpdate(Mutation):

    class Arguments:
        case_id = NonNull(Float)

        name = String()
        description = String()
        soc_id = String()
        classification_id = String()
        severity_id = Int()
        client = Int()

    case = Field(CaseObject)

    @staticmethod
    def mutate(root, info, case_id, name=None, soc_id=None, classification_id=None, client=None, description=None, severity_id=None ):
        request = {}
        if name:
            request['case_name'] = name
        if soc_id:
            request['case_soc_id'] = soc_id
        if classification_id:
            request['classification_id'] = classification_id
        if client:
            request['case_customer'] = client
        if description:
            request['case_description'] = description
        if severity_id:
            request['severity_id'] = severity_id
        case, _ = update(case_id, request)
        return CaseUpdate(case=case)
