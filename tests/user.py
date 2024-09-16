#  Copyright (C) 2023 - DFIR-IRIS
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

from graphql_api import GraphQLApi
from rest_api import RestApi


class User:

    def __init__(self, iris_url, api_key, identifier):
        self._graphql_api = GraphQLApi(iris_url + '/graphql', api_key)
        self._api = RestApi(iris_url, api_key)
        self._identifier = identifier

    def get_identifier(self):
        return self._identifier

    def execute_graphql_query(self, payload):
        response = self._graphql_api.execute(payload)
        body = response.json()
        print(f'{payload} => {body}')
        return body

    def create(self, path, payload):
        return self._api.post(path, payload)

    def get(self, path):
        return self._api.get(path)

    def delete(self, path):
        return self._api.delete(path)
