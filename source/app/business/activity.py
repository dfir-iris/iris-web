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

from app.business.war_rooms_access import ac_get_fast_user_war_rooms_access
from app.datamgmt.activities.activities_db import list_activities_paginated
from app.datamgmt.activities.activities_db import search_users_activity_in_case
from app.datamgmt.manage.manage_cases_db import user_list_cases_view


def activity_search_in_case(case_identifier):
    return search_users_activity_in_case(case_identifier)


def list_activities(
        user_id,
        can_read_all,
        page=1,
        per_page=25,
        include_non_case=False,
        search_value=None,
        scope_user_id=None,
        case_id=None,
        war_room_id=None,
        user_ids=None,
        case_ids=None,
        war_room_ids=None,
        date_from=None,
        date_to=None,
        is_from_api=None,
        is_manual=None,
):
    """Paginated, access-scoped activities listing for the Activities page.

    ``can_read_all`` indicates whether the caller holds the
    ``all_activities_read`` permission. When False, results are scoped to
    cases the caller has access to (matching the legacy behaviour of
    ``/activities/list``). When True, the caller sees activity across every
    case (the legacy ``/activities/list-all`` view) and can opt-in to
    non-case-related rows via ``include_non_case``.
    """
    page = max(1, int(page or 1))
    per_page = max(1, min(int(per_page or 25), 200))

    if can_read_all:
        accessible_case_ids = None
        accessible_war_room_ids = None
    else:
        # `user_list_cases_view` returns the case ids the user can see.
        # Pass through verbatim — `list_activities_paginated` understands
        # an empty list as "no cases" and short-circuits accordingly.
        accessible_case_ids = user_list_cases_view(user_id)
        # War-room access lives on its own ACL table (see
        # `war_rooms_access`), independent of case ACLs.
        accessible_war_room_ids = ac_get_fast_user_war_rooms_access(user_id)

    # When the caller asks for specific cases but isn't a global reader,
    # intersect their request with the accessible-case window so a guess
    # at a forbidden case id silently no-ops (rather than 403'ing or
    # leaking existence).
    effective_case_ids = case_ids
    if not can_read_all and case_ids:
        accessible_set = set(accessible_case_ids or [])
        effective_case_ids = [cid for cid in case_ids if cid in accessible_set]
        if not effective_case_ids:
            # The caller filtered down to cases they can't see — return
            # an empty page by passing an unsatisfiable case filter,
            # rather than dropping the filter and showing everything.
            effective_case_ids = [-1]

    effective_war_room_ids = war_room_ids
    if not can_read_all and war_room_ids:
        accessible_wr_set = set(accessible_war_room_ids or [])
        effective_war_room_ids = [wid for wid in war_room_ids if wid in accessible_wr_set]
        if not effective_war_room_ids:
            effective_war_room_ids = [-1]

    return list_activities_paginated(
        page=page,
        per_page=per_page,
        accessible_case_ids=accessible_case_ids,
        accessible_war_room_ids=accessible_war_room_ids,
        include_non_case=include_non_case,
        search_value=search_value or None,
        user_id=scope_user_id,
        case_id=case_id,
        war_room_id=war_room_id,
        user_ids=user_ids,
        case_ids=effective_case_ids,
        war_room_ids=effective_war_room_ids,
        date_from=date_from,
        date_to=date_to,
        is_from_api=is_from_api,
        is_manual=is_manual,
    )
