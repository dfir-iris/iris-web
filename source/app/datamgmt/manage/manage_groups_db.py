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
from flask_login import current_user
from sqlalchemy import and_

from app import db
from app.datamgmt.case.case_db import get_case
from app.datamgmt.manage.manage_cases_db import list_cases_id
from app.iris_engine.access_control.utils import ac_access_level_mask_from_val_list, ac_ldp_group_removal
from app.iris_engine.access_control.utils import ac_access_level_to_list
from app.iris_engine.access_control.utils import ac_auto_update_user_effective_access
from app.iris_engine.access_control.utils import ac_permission_to_list
from app.models import Cases
from app.models.authorization import Group
from app.models.authorization import GroupCaseAccess
from app.models.authorization import User
from app.models.authorization import UserGroup
from app.schema.marshables import AuthorizationGroupSchema


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

    groups = AuthorizationGroupSchema().dump(groups, many=True)
    for group in groups:
        perms = ac_permission_to_list(group['group_permissions'])
        group['group_permissions_list'] = perms
        group['group_members'] = membership_list.get(group['group_id'], [])

    return groups


def get_group(group_id):
    group = Group.query.filter(Group.group_id == group_id).first()

    return group


def get_group_by_name(group_name):
    groups = Group.query.filter(Group.group_name == group_name)
    return groups.first()


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

    perms = ac_permission_to_list(group.group_permissions)
    setattr(group, 'group_permissions_list', perms)
    setattr(group, 'group_members', membership_list.get(group.group_id, []))

    return group


def get_group_details(group_id):
    group = get_group_with_members(group_id)
    if not group:
        return group

    group_accesses = GroupCaseAccess.query.with_entities(
        GroupCaseAccess.access_level,
        GroupCaseAccess.case_id,
        Cases.name.label('case_name')
    ).join(
        GroupCaseAccess.case
    ).filter(
        GroupCaseAccess.group_id == group_id
    ).all()

    group_cases_access = []
    for kgroup in group_accesses:
        group_cases_access.append({
            "access_level": kgroup.access_level,
            "access_level_list": ac_access_level_to_list(kgroup.access_level),
            "case_id": kgroup.case_id,
            "case_name": kgroup.case_name
        })

    setattr(group, 'group_cases_access', group_cases_access)

    return group


def update_group_members(group, members):
    if not group:
        return None

    cur_groups = UserGroup.query.with_entities(
        UserGroup.user_id
    ).filter(UserGroup.group_id == group.group_id).all()

    set_cur_groups = set([grp[0] for grp in cur_groups])
    set_members = set(int(mber) for mber in members)

    users_to_add = set_members - set_cur_groups
    users_to_remove = set_cur_groups - set_members

    for uid in users_to_add:
        user = User.query.filter(User.id == uid).first()
        if user:
            ug = UserGroup()
            ug.group_id = group.group_id
            ug.user_id = user.id
            db.session.add(ug)

        db.session.commit()
        ac_auto_update_user_effective_access(uid)

    for uid in users_to_remove:
        if current_user.id == uid and ac_ldp_group_removal(uid, group.group_id):
            continue

        UserGroup.query.filter(
            and_(UserGroup.group_id == group.group_id,
                 UserGroup.user_id == uid)
        ).delete()

        db.session.commit()
        ac_auto_update_user_effective_access(uid)

    return group


def remove_user_from_group(group, member):
    if not group:
        return None

    UserGroup.query.filter(
        and_(UserGroup.group_id == group.group_id,
             UserGroup.user_id == member.id)
    ).delete()
    db.session.commit()

    ac_auto_update_user_effective_access(member.id)

    return group


def delete_group(group):
    if not group:
        return None

    UserGroup.query.filter(UserGroup.group_id == group.group_id).delete()
    GroupCaseAccess.query.filter(GroupCaseAccess.group_id == group.group_id).delete()

    db.session.delete(group)
    db.session.commit()


def add_case_access_to_group(group, cases_list, access_level):
    if not group:
        return None, "Invalid group"

    for case_id in cases_list:
        case = get_case(case_id)
        if not case:
            return None, "Invalid case ID"

        access_level_mask = ac_access_level_mask_from_val_list([access_level])

        ocas = GroupCaseAccess.query.filter(
            and_(
                GroupCaseAccess.case_id == case_id,
                GroupCaseAccess.group_id == group.group_id
            )).all()
        if ocas:
            for oca in ocas:
                db.session.delete(oca)

        oca = GroupCaseAccess()
        oca.group_id = group.group_id
        oca.access_level = access_level_mask
        oca.case_id = case_id
        db.session.add(oca)

    db.session.commit()

    return group, "Updated"


def add_all_cases_access_to_group(group, access_level):
    if not group:
        return None, "Invalid group"

    for case_id in list_cases_id():
        access_level_mask = ac_access_level_mask_from_val_list([access_level])

        ocas = GroupCaseAccess.query.filter(
            and_(
                GroupCaseAccess.case_id == case_id,
                GroupCaseAccess.group_id == group.group_id
            )).all()
        if ocas:
            for oca in ocas:
                db.session.delete(oca)

        oca = GroupCaseAccess()
        oca.group_id = group.group_id
        oca.access_level = access_level_mask
        oca.case_id = case_id
        db.session.add(oca)

    db.session.commit()
    return group, "Updated"


def remove_case_access_from_group(group_id, case_id):
    if not group_id or type(group_id) is not int:
        return

    if not case_id or type(case_id) is not int:
        return

    GroupCaseAccess.query.filter(
        and_(
            GroupCaseAccess.case_id == case_id,
            GroupCaseAccess.group_id == group_id
        )).delete()

    db.session.commit()
    return


def remove_cases_access_from_group(group_id, cases_list):
    if not group_id or type(group_id) is not int:
        return False, "Invalid group"

    if not cases_list or type(cases_list[0]) is not int:
        return False, "Invalid cases list"

    GroupCaseAccess.query.filter(
        and_(
            GroupCaseAccess.case_id.in_(cases_list),
            GroupCaseAccess.group_id == group_id
        )).delete()

    db.session.commit()

    return True, "Updated"
