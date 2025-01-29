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

from app.models.pagination_parameters import PaginationParameters


def parse_comma_separated_identifiers(identifiers: str):
    return [int(identifier) for identifier in identifiers.split(',')]


def parse_boolean(parameter: str):
    if parameter == 'true':
        return True
    if parameter == 'false':
        return False
    raise ValueError(f'Expected true or false, got {parameter}')


def parse_pagination_parameters(request) -> PaginationParameters:
    arguments = request.args
    page = arguments.get('page', 1, type=int)
    per_page = arguments.get('per_page', 10, type=int)
    order_by = arguments.get('order_by', type=str)
    sort_dir = arguments.get('sort_dir', 'asc', type=str)

    return PaginationParameters(page, per_page, order_by, sort_dir)
