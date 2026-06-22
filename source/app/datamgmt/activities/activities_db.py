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
