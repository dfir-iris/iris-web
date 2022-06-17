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
from sqlalchemy import and_

from app import db
from app.iris_engine.access_control.utils import ac_permission_to_list
from app.models.authorization import Group
from app.models.authorization import GroupCaseAccess
from app.models.authorization import Organisation
from app.models.authorization import User
from app.models.authorization import UserGroup
from app.models.authorization import UserOrganisation


def get_organisations_list():
    orgs = Organisation.query.all()

    return orgs


def get_org(org_id):
    group = Organisation.query.filter(Organisation.org_id == org_id).first()

    return group


def get_org_with_members(org_id):
    org = get_org(org_id)
    if not org:
        return None

    get_membership_list = UserOrganisation.query.with_entities(
        Organisation.org_id,
        User.user,
        User.id,
        User.name
    ).join(
        UserOrganisation.user
    ).filter(
        UserOrganisation.org_id == org_id
    ).all()

    membership_list = {}
    for member in get_membership_list:
        if member.org_id not in membership_list:

            membership_list[member.org_id] = [{
                'user': member.user,
                'name': member.name,
                'id': member.id
            }]
        else:
            membership_list[member.org_id].append({
                'user': member.user,
                'name': member.name,
                'id': member.id
            })

    setattr(org, 'org_members', membership_list.get(org.org_id, []))

    return org


def update_group_members(group, members):
    if not group:
        return None

    UserGroup.query.filter(UserGroup.group_id == group.group_id).delete()

    for uid in set(members):
        user = User.query.filter(User.id == uid).first()
        if user:
            ug = UserGroup()
            ug.group_id = group.group_id
            ug.user_id = user.id
            db.session.add(ug)

    db.session.commit()

    return group


def remove_user_from_group(group, member):
    if not group:
        return None

    UserGroup.query.filter(
        and_(UserGroup.group_id == group.group_id,
                UserGroup.user_id == member.id)
    ).delete()

    db.session.commit()

    return group


def delete_group(group):
    if not group:
        return None

    UserGroup.query.filter(UserGroup.group_id == group.group_id).delete()
    GroupCaseAccess.query.filter(GroupCaseAccess.group_id == group.group_id).delete()

    db.session.delete(group)
    db.session.commit()
