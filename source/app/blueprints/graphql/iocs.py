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
from graphene import Mutation
from graphene import ID
from graphene import NonNull

from app.models.models import Ioc


class IocObject(SQLAlchemyObjectType):
    class Meta:
        model = Ioc


class AddIoc(Mutation):

    class Arguments:
        # note: I prefer NonNull rather than the syntax required=True
        caseId: NonNull(ID)
        #typeId: 1
        #tlpId: 1
        #value: "8.8.8.8"
        #description: "some description"
        #tags:

    @staticmethod
    def mutate(root, info, title, description, year, username):
        author = Author.query.filter_by(username=username).first()
        book = Book(title=title, description=description, year=year)
        if author is not None:
            book.author = author
        db.session.add(book)
        db.session.commit()
        return AddBook(book=book)