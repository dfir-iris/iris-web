#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
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
from sqlalchemy import desc
from sqlalchemy import func

from app.models.cases import Cases
from app.models.authorization import User
from app.models.models import UserActivity


def get_auto_activities(caseid):
    """
    DB function to fetch the automatically generated activities
    caseid: the case from which to get activities
    """
    auto_activities = UserActivity.query.with_entities(
        User.name.label('user_name'),
        UserActivity.activity_date,
        UserActivity.activity_desc,
        UserActivity.user_input
    ).join(
        UserActivity.user
    ).filter(
        and_(
            UserActivity.case_id == caseid,
            UserActivity.activity_desc.notlike('[Unbound]%'),
            UserActivity.activity_desc.notlike('Started a search for %'),
            UserActivity.activity_desc.notlike('Updated global task %'),
            UserActivity.activity_desc.notlike('Created new global task %'),
            UserActivity.activity_desc.notlike('Started a new case creation %'),
            UserActivity.user_input == False
        )
    ).order_by(
        UserActivity.activity_date
    ).all()

    auto_activities = [row._asdict() for row in auto_activities]

    return auto_activities


def get_manual_activities(caseid):
    """
    DB function to fetch the manually generated activities
    caseid: the case from which to get activities
    """
    manual_activities = UserActivity.query.with_entities(
        User.name.label("user_name"),
        UserActivity.activity_date,
        UserActivity.activity_desc,
        UserActivity.user_input
    ).join(
        UserActivity.user
    ).filter(
        and_(
            UserActivity.case_id == caseid,
            UserActivity.user_input == True
        )
    ).order_by(
        UserActivity.activity_date
    ).all()

    manual_activities = [row._asdict() for row in manual_activities]

    return manual_activities


def get_users_activities():
    user_activities = UserActivity.query.with_entities(
        Cases.name.label("case_name"),
        User.name.label("user_name"),
        UserActivity.user_id,
        UserActivity.case_id,
        UserActivity.activity_date,
        UserActivity.activity_desc,
        UserActivity.user_input,
        UserActivity.is_from_api
    ).filter(
        UserActivity.display_in_ui == True
    ).outerjoin(
        UserActivity.user
    ).outerjoin(
        UserActivity.case
    ).order_by(desc(UserActivity.activity_date)).limit(10000).all()

    return user_activities


def get_all_users_activities():
    user_activities = UserActivity.query.with_entities(
        Cases.name.label("case_name"),
        User.name.label("user_name"),
        UserActivity.user_id,
        UserActivity.case_id,
        UserActivity.activity_date,
        UserActivity.activity_desc,
        UserActivity.user_input,
        UserActivity.is_from_api
    ).join(
        UserActivity.case
    ).join(
        UserActivity.user
    ).order_by(desc(UserActivity.activity_date)).limit(10000).all()

    user_activities += UserActivity.query.with_entities(
        UserActivity.case_id.label("case_name"),
        UserActivity.user_id.label("user_name"),
        UserActivity.activity_date,
        UserActivity.activity_desc,
        UserActivity.user_input,
        UserActivity.is_from_api
    ).filter(and_(
        UserActivity.case_id == None
    )).order_by(desc(UserActivity.activity_date)).limit(10000).all()

    return user_activities


def get_recent_activities_for_user(user_id, limit=20, offset=0, accessible_case_ids=None):
    """Recent UI-visible UserActivity entries that the given user is allowed
    to see, ordered newest-first.

    Filters on the same `display_in_ui` flag the legacy global activity
    feed uses, then scopes by `case_id IN (...)` so users only see entries
    from cases they have access to (or rows authored by the user
    themselves). Activity from *other* users on those same cases is
    included — this is the whole point: the feed is "what's happening on
    the cases I'm part of", not "what I'm doing".

    `offset` lets callers paginate by re-querying with `offset += limit`
    until fewer than `limit` rows come back.

    Pass `accessible_case_ids` to avoid an extra lookup if the caller has
    already computed it.
    """
    if accessible_case_ids is None:
        from app.datamgmt.manage.manage_cases_db import user_list_cases_view
        accessible_case_ids = user_list_cases_view(user_id)

    case_filter = UserActivity.case_id.in_(accessible_case_ids) if accessible_case_ids else None

    base = UserActivity.query.with_entities(
        UserActivity.id,
        Cases.name.label('case_name'),
        UserActivity.case_id,
        User.name.label('user_name'),
        UserActivity.user_id,
        UserActivity.activity_date,
        UserActivity.activity_desc,
        UserActivity.user_input,
        UserActivity.is_from_api
    ).outerjoin(
        UserActivity.user
    ).outerjoin(
        UserActivity.case
    ).filter(
        UserActivity.display_in_ui == True
    )

    if case_filter is not None:
        # Show activity from accessible cases plus activity authored by the
        # user themselves on cases they no longer have access to (so users
        # don't lose their own recent history when scopes shift).
        base = base.filter(
            (case_filter) | (UserActivity.user_id == user_id)
        )
    else:
        base = base.filter(UserActivity.user_id == user_id)

    rows = base.order_by(desc(UserActivity.activity_date)).offset(offset).limit(limit).all()

    return [row._asdict() for row in rows]


def list_activities_paginated(
        page=1,
        per_page=25,
        accessible_case_ids=None,
        include_non_case=False,
        search_value=None,
        user_id=None,
        case_id=None,
        user_ids=None,
        case_ids=None,
        date_from=None,
        date_to=None,
        is_from_api=None,
        is_manual=None,
):
    """Paginated, filtered listing of UserActivity rows for the Activities
    page.

    Same row shape as ``get_users_activities`` / ``get_all_users_activities``
    but with proper pagination, optional access scoping, and an optional
    text filter on ``activity_desc``. Mirrors the shape used elsewhere in
    the v2 API (returns a ``Pagination`` object so callers can hand it
    straight to ``response_api_paginated``).

    Args:
        page: 1-indexed page number.
        per_page: page size (caller is expected to clamp).
        accessible_case_ids:
            * ``None``  → no access filter (caller is admin / has the
              ``all_activities_read`` permission).
            * iterable  → only rows whose ``case_id`` is in the list, or
              (when ``include_non_case`` is True) rows with ``case_id IS
              NULL`` regardless.
        include_non_case:
            if True, also include rows with no associated case (login
            events, global task changes, etc). When False, only
            case-linked activity is returned.
        search_value: optional case-insensitive ILIKE filter on the
            ``activity_desc`` column.
        user_id: optional — restrict to a single user.
        case_id: optional — restrict to a single case.
    """

    # The UserActivity table accumulates near-duplicate rows whenever a
    # client emits the same change repeatedly within seconds (e.g. a
    # note editor's debounced autosave, an alert ingestion script
    # re-emitting on retry). For the listing page we collapse rows that
    # share (user_id, case_id, activity_desc) within a one-minute bucket
    # and surface a single representative row carrying the most-recent
    # timestamp plus an `occurrences` count. This is identical to how
    # most activity feeds (GitHub, Slack) coalesce bursts.
    bucket = func.date_trunc('minute', UserActivity.activity_date).label('bucket')

    base = UserActivity.query.filter(UserActivity.display_in_ui == True)

    if accessible_case_ids is not None:
        # Empty list ⇒ no accessible cases. If the caller also wants
        # non-case-related rows, allow only those; otherwise short-
        # circuit to an empty page.
        if not accessible_case_ids:
            if include_non_case:
                base = base.filter(UserActivity.case_id.is_(None))
            else:
                base = base.filter(False)
        else:
            scope = UserActivity.case_id.in_(accessible_case_ids)
            if include_non_case:
                scope = scope | UserActivity.case_id.is_(None)
            base = base.filter(scope)
    elif not include_non_case:
        # Admin view but the caller doesn't want non-case rows.
        base = base.filter(UserActivity.case_id.isnot(None))

    if search_value:
        base = base.filter(UserActivity.activity_desc.ilike(f'%{search_value}%'))

    if user_id is not None:
        base = base.filter(UserActivity.user_id == user_id)

    if case_id is not None:
        base = base.filter(UserActivity.case_id == case_id)

    # Multi-value filters. We accept the singular forms above too (legacy
    # callers) and additively intersect with the multi-value ones — that
    # way the UI can drive everything through the list params without
    # needing to fall back to the singular shape.
    if user_ids:
        base = base.filter(UserActivity.user_id.in_(list(user_ids)))

    if case_ids:
        # Intersect with the access-scoped list when one is in effect so
        # an admin filter on cases X+Y still respects a non-admin's
        # accessible-case window if both were passed.
        base = base.filter(UserActivity.case_id.in_(list(case_ids)))

    if date_from is not None:
        base = base.filter(UserActivity.activity_date >= date_from)

    if date_to is not None:
        base = base.filter(UserActivity.activity_date <= date_to)

    if is_from_api is not None:
        base = base.filter(UserActivity.is_from_api == bool(is_from_api))

    if is_manual is not None:
        base = base.filter(UserActivity.user_input == bool(is_manual))

    # Aggregation step. We pick MAX(id) as the representative row id so
    # the frontend has a stable key for keyed-each updates; MAX(date) is
    # the cluster's effective timestamp. `bool_or` collapses the two
    # boolean flags — within a duplicate cluster they should be uniform
    # anyway, but `bool_or` is correct if they ever diverge (e.g. one
    # row came in via API, one via UI, for the same logical change).
    aggregated = base.with_entities(
        func.max(UserActivity.id).label('id'),
        UserActivity.case_id,
        UserActivity.user_id,
        UserActivity.activity_desc,
        bucket,
        func.max(UserActivity.activity_date).label('activity_date'),
        func.bool_or(UserActivity.user_input).label('user_input'),
        func.bool_or(UserActivity.is_from_api).label('is_from_api'),
        func.count().label('occurrences'),
    ).group_by(
        UserActivity.case_id,
        UserActivity.user_id,
        UserActivity.activity_desc,
        bucket,
    ).subquery()

    # Re-attach friendly labels. We outer-join because user / case may
    # be NULL (login events, global tasks; or users that were deleted
    # after writing the row — UserActivity.user_id is nullable).
    listing = (
        UserActivity.query.session.query(
            aggregated.c.id,
            Cases.name.label('case_name'),
            aggregated.c.case_id,
            User.name.label('user_name'),
            aggregated.c.user_id,
            aggregated.c.activity_date,
            aggregated.c.activity_desc,
            aggregated.c.user_input,
            aggregated.c.is_from_api,
            aggregated.c.occurrences,
        )
        .outerjoin(User, User.id == aggregated.c.user_id)
        .outerjoin(Cases, Cases.case_id == aggregated.c.case_id)
        .order_by(desc(aggregated.c.activity_date))
    )

    return listing.paginate(page=page, per_page=per_page, error_out=False)


def search_users_activity_in_case(case_identifier):
    ua = UserActivity.query.with_entities(
        UserActivity.activity_date,
        User.name,
        UserActivity.activity_desc,
        UserActivity.is_from_api
    ).filter(and_(
        UserActivity.case_id == case_identifier,
        UserActivity.display_in_ui == True
    )).join(
        UserActivity.user
    ).order_by(
        desc(UserActivity.activity_date)
    ).limit(40).all()

    return [a._asdict() for a in ua]
