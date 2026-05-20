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
from app.datamgmt.db_operations import db_create
from app.models.authorization import Group
from app.iris_engine.utils.tracker import track_activity
from app.datamgmt.manage.manage_groups_db import get_group_details, get_group_by_name
from app.datamgmt.manage.manage_groups_db import update_group
from app.datamgmt.manage.manage_groups_db import delete_group
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.iris_engine.access_control.utils import ac_ldp_group_removal


def groups_create(group: Group) -> Group:
    db_create(group)
    track_activity(f'added group {group.group_name}', ctx_less=True)

    return group


def groups_get(identifier) -> Group:
    group = get_group_details(identifier)
    if not group:
        raise ObjectNotFoundError()
    return group


def groups_get_by_name(name) -> Group:
    group = get_group_by_name(name)
    if not group:
        raise ObjectNotFoundError()
    return group


def groups_exist(identifier) -> bool:
    group = get_group_details(identifier)
    return group is not None


def groups_update():
    update_group()


def groups_delete(current_user, group: Group):
    if ac_ldp_group_removal(current_user.id, group_id=group.group_id):
        raise BusinessProcessingError('I can\'t let you do that Dave', data='Removing this group will lock you out')
    delete_group(group)
