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

from sqlalchemy import and_

from app.models.models import SavedFilter


def get_filter_by_id(user_identifier, filter_id):
    """
    Get a filter by its ID

    args:
        filter_id: the ID of the filter to get

    returns:
        SavedFilter object
    """
    saved_filter = SavedFilter.query.filter(SavedFilter.filter_id == filter_id).first()
    if saved_filter:
        if saved_filter.filter_is_private and saved_filter.created_by != user_identifier:
            return None

    return saved_filter


def list_filters_by_type(user_identifier, filter_type, include_public=True):
    """
    List filters by type

    args:
        user_identifier: user id
        filter_type: the type of filter to list
        include_public: whether to include non-private filters

    returns:
        List of SavedFilter objects
    """
    private_filters_for_user = SavedFilter.query.filter(
        and_(
            SavedFilter.filter_is_private == True,
            SavedFilter.created_by == user_identifier,
            SavedFilter.filter_type == filter_type
        )
    )

    if not include_public:
        return private_filters_for_user.all()

    public_filters = SavedFilter.query.filter(
        SavedFilter.filter_is_private == False,
        SavedFilter.filter_type == filter_type
    )

    all_filters = public_filters.union_all(private_filters_for_user).all()

    return all_filters


def get_filters(user_id, filter_type="alerts", include_public=True):
    return list_filters_by_type(user_id, filter_type, include_public)
