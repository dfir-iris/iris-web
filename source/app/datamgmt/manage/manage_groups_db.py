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
from app.iris_engine.access_control.utils import ac_permission_to_list
from app.models.authorization import Group
from app.models.authorization import User
from app.models.authorization import UserGroup


def get_groups_list():
    groups = Group.query.all()

    return groups


def get_groups_list_hr_perms():
    groups = get_groups_list()

    get_membership_list = UserGroup.query.with_entities(
        UserGroup.group_id,
        User.user,
        User.id,
        User.name
    ).join(UserGroup.user).all()

    membership_list = {}
    for member in get_membership_list:
        if member.group_id not in membership_list:
            membership_list[member.group_id] = [{
                'user': member.user,
                'name': member.name,
                'id': member.id
            }]
        else:
            membership_list[member.group_id].append({
                'user': member.user,
                'name': member.name,
                'id': member.id
            })

    for group in groups:
        perms = ac_permission_to_list(group.group_permissions)
        setattr(group, 'group_permissions_list', perms)
        setattr(group, 'group_members', membership_list.get(group.group_id, []))

    return groups


def get_group(group_id):
    group = Group.query.filter(Group.group_id == group_id).first()

    return group


def get_group_with_members(group_id):
    group = get_group(group_id)
    if not group:
        return None

    get_membership_list = UserGroup.query.with_entities(
        UserGroup.group_id,
        User.user,
        User.id,
        User.name
    ).join(
        UserGroup.user
    ).filter(
        UserGroup.group_id == group_id
    ).all()

    membership_list = {}
    for member in get_membership_list:
        if member.group_id not in membership_list:
            print(dir(member))
            membership_list[member.group_id] = [{
                'user': member.user,
                'name': member.name,
                'id': member.id
            }]
        else:
            membership_list[member.group_id].append({
                'user': member.user,
                'name': member.name,
                'id': member.id
            })

    setattr(group, 'group_members', membership_list.get(group.group_id, []))

    return group
