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
from graphene import Float
from graphene import String

from app.models.models import Ioc
from app.business.iocs import create
from app.business.iocs import delete

class IocObject(SQLAlchemyObjectType):
    class Meta:
        model = Ioc


class IOCCreate(Mutation):

    class Arguments:
        # note: it seems really too difficult to work with IDs.
        #       I don't understand why graphql_relay.from_global_id does not seem to work...
        # note: I prefer NonNull rather than the syntax required=True
        case_id = NonNull(Float)
        type_id = NonNull(Int)
        tlp_id = NonNull(Int)
        value = NonNull(String)
        description = String()
        tags = String()

    ioc = Field(IocObject)

    @staticmethod
    def mutate(root, info, case_id, type_id, tlp_id, value, description=None, tags=None):
        request = {
            'ioc_type_id': type_id,
            'ioc_tlp_id': tlp_id,
            'ioc_value': value,
            'ioc_description': description,
            'ioc_tags': tags
        }
        ioc, _ = create(request, case_id)
        return IOCCreate(ioc=ioc)


# TODO: this mutation does both IOC creation and IOC link onto case: maybe we should distinguish the two actions
class IOCDelete(Mutation):
    class Arguments:
        ioc_id = NonNull(Float)
        case_id = NonNull(Float)

    message = String()

    @staticmethod
    def mutate(root, info, ioc_id, case_id):
        message = delete(ioc_id, case_id)
        return IOCDelete(message=message)
