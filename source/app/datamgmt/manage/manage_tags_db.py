#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
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

from functools import reduce

from sqlalchemy import and_
from flask_sqlalchemy.pagination import Pagination

from app.db import db
from app.logger import logger
from app.models.models import Tags
from app.datamgmt.conversions import convert_sort_direction
from app.models.pagination_parameters import PaginationParameters


def get_filtered_tags(tag_title, tag_namespace, pagination_parameters: PaginationParameters) -> Pagination:

    conditions = []
    if tag_title:
        conditions.append(Tags.tag_title.ilike(f'%{tag_title}%'))

    if tag_namespace:
        conditions.append(Tags.tag_namespace.ilike(f'%{tag_namespace}%'))

    if len(conditions) > 1:
        conditions = [reduce(and_, conditions)]

    data = Tags.query.filter(*conditions)

    sort_by = pagination_parameters.get_order_by()
    if sort_by is not None:
        order_func = convert_sort_direction(pagination_parameters.get_direction())

        if sort_by == 'name':
            data = data.order_by(order_func(Tags.tag_title))
        elif sort_by == 'namespace':
            data = data.order_by(order_func(Tags.tag_namespace))
        else:
            data = data.order_by(order_func(Tags.tag_title))

    try:

        filtered_tags = data.paginate(page=pagination_parameters.get_page(), per_page=pagination_parameters.get_per_page())

    except Exception as e:
        logger.exception(f"Failed to get filtered tags: {e}")
        raise e

    return filtered_tags


def add_db_tag(tag_title, tag_namespace=None):
    """
    Adds a tag to the database.

    :param tag_title: Tag title
    :param tag_namespace: Tag namespace
    :return: Tag ID
    """

    tag = Tags(tag_title=tag_title, namespace=tag_namespace)

    try:
        # Only add the tag if it doesn't already exist
        existing_tag = Tags.query.filter_by(tag_title=tag_title).first()
        if existing_tag:
            return existing_tag

        tag.save()
        db.session.commit()

    except Exception as e:
        logger.exception(f"Failed to add tag: {e}")
        raise e

    return tag
