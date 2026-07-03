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

from app.db import db
from app.datamgmt.filters.filters_db import get_filters, get_filter_by_id
from app.iris_engine.utils.tracker import track_activity
from app.models.errors import ObjectNotFoundError


def _filter_label(saved_filter):
    return getattr(saved_filter, 'filter_name', None) or f'#{getattr(saved_filter, "id", "?")}'


def alert_filter_add(new_saved_filter):
    db.session.add(new_saved_filter)
    db.session.commit()
    track_activity(f'created saved filter "{_filter_label(new_saved_filter)}"')


def alert_filter_list(user, filter_type="alerts", include_public=True):
    filters = get_filters(
        user_id=user.id,
        filter_type=filter_type,
        include_public=include_public
    )
    return filters


def alert_filter_get(user, identifier):
    alert_filter = get_filter_by_id(user.id, identifier)
    if not alert_filter:
        raise ObjectNotFoundError()
    return alert_filter


def alert_filter_update():
    db.session.commit()
    track_activity('updated a saved filter')


def alert_filter_delete(saved_filter):
    label = _filter_label(saved_filter)
    db.session.delete(saved_filter)
    db.session.commit()
    track_activity(f'deleted saved filter "{label}"')
