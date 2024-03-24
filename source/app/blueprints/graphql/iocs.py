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
from graphene import Field
from graphene import Mutation
from graphene import NonNull
from graphene import Int
from graphene import String

from app.models.models import Ioc
from app.business.iocs import create


class IocObject(SQLAlchemyObjectType):
    class Meta:
        model = Ioc


class AddIoc(Mutation):

    class Arguments:
        # TODO: it seems really too difficult to work with IDs.
        #       I don't understand why graphql_relay.from_global_id does not seem to work...
        # note: I prefer NonNull rather than the syntax required=True
        # TODO: Integers in graphql are only 32 bits. => will this be a problem? Should we use either float or string?
        case_id = NonNull(Int)
        type_id = NonNull(Int)
        tlp_id = NonNull(Int)
        value = NonNull(String)
        # TODO add these non mandatory arguments
        #description =
        #tags =

    ioc = Field(IocObject)

    @staticmethod
    def mutate(root, info, case_id, type_id, tlp_id, value):
        request = {
            'ioc_type_id': type_id,
            'ioc_tlp_id': tlp_id,
            'ioc_value': value
        }
        ioc, _ = create(request, case_id)
        return AddIoc(ioc=ioc)
