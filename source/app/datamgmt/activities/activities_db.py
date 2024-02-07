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

from app.models import Cases
from app.models.authorization import User
from app.models.models import UserActivity


def get_auto_activities(caseid):
    """
    DB function to fetch the automatically generated activities
    caseid: the case from which to get activities
    """
    auto_activities = UserActivity.query.with_entities(
        User.name.label("user_name"),
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
