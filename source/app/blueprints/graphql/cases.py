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
from graphene.relay import Node
from graphene import Field
from graphene import Mutation
from graphene import NonNull
from graphene import Int
from graphene import String
from graphene import Text

from app.models.cases import Cases
from app.business.cases import create


class CaseObject(SQLAlchemyObjectType):
    class Meta:
        model = Cases
        interfaces = [Node]

class AddCase(Mutation):

    class Arguments:
        case_id = NonNull(Int)
        client = NonNull(Text)
        name = NonNull(String)
        description = NonNull(Text)

        # TODO add these non mandatory arguments
        #soc_id = NonNull(Int)

    case = Field(CaseObject)

    @staticmethod
    def mutate(root, info, case_id, client, name, description):
        request = {
            'case_client': client,
            'case_name': name,
            'case_description': description
        }
        case, _ = create(request, case_id)
        return AddCase(case=case)