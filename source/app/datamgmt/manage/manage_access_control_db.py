#!/usr/bin/env python3
#
#  IRIS Source Code
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
from app.models import Cases
from app.models.authorization import Group
from app.models.authorization import GroupCaseAccess
from app.models.authorization import Organisation
from app.models.authorization import OrganisationCaseAccess
from app.models.authorization import User
from app.models.authorization import UserCaseAccess


def manage_ac_audit_users_db():
    uca = UserCaseAccess.query.with_entities(
        User.name,
        User.user,
        User.id,
        User.uuid,
        UserCaseAccess.access_level,
        Cases.name,
        Cases.case_id
    ).join(
        UserCaseAccess.case,
        UserCaseAccess.user
    ).all()

    gca = GroupCaseAccess.query.with_entities(
        Group.group_name,
        Group.group_id,
        Group.group_uuid,
        GroupCaseAccess.access_level,
        Cases.name,
        Cases.case_id
    ).join(
        GroupCaseAccess.case,
        GroupCaseAccess.group
    ).all()

    oca = OrganisationCaseAccess.query.with_entities(
        Organisation.org_name,
        Organisation.org_id,
        Organisation.org_uuid,
        OrganisationCaseAccess.access_level,
        Cases.name,
        Cases.case_id
    ).all()

    ret = {
        'users': [u._asdict() for u in uca],
        'groups': [g._asdict() for g in gca],
        'organisations': [o._asdict() for o in oca]
    }

    return ret


