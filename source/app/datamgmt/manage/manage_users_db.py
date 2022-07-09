#!/usr/bin/env python3
#
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

from app import bc
from app import db
from app.datamgmt.case.case_db import get_case
from app.iris_engine.access_control.utils import ac_access_level_mask_from_val_list
from app.iris_engine.access_control.utils import ac_access_level_to_list
from app.iris_engine.access_control.utils import ac_auto_update_user_effective_access
from app.iris_engine.access_control.utils import ac_get_detailed_effective_permissions_from_groups
from app.models import Cases
from app.models.authorization import Group
from app.models.authorization import Organisation
from app.models.authorization import User
from app.models.authorization import UserCaseAccess
from app.models.authorization import UserCaseEffectiveAccess
from app.models.authorization import UserGroup
from app.models.authorization import UserOrganisation


def get_user(user_id, id_key: str = 'id'):
    user = User.query.filter(getattr(User, id_key) == user_id).first()
    return user


def get_user_effective_permissions(user_id):
    groups_perms = UserGroup.query.with_entities(
        Group.group_permissions,
        Group.group_name
    ).filter(
        UserGroup.user_id == user_id
    ).join(
        UserGroup.group
    ).all()

    effective_permissions = ac_get_detailed_effective_permissions_from_groups(groups_perms)

    return effective_permissions


def get_user_groups(user_id):
    groups = UserGroup.query.with_entities(
        Group.group_name,
        Group.group_id,
        Group.group_uuid
    ).filter(
        UserGroup.user_id == user_id
    ).join(
        UserGroup.group
    ).all()

    output = []
    for group in groups:
        output.append(group._asdict())

    return output


def update_user_groups(user_id, groups):
    cur_groups = UserGroup.query.with_entities(
        UserGroup.group_id
    ).filter(UserGroup.user_id == user_id).all()

    set_cur_groups = set([grp[0] for grp in cur_groups])
    set_new_groups = set(int(grp) for grp in groups)

    groups_to_add = set_new_groups - set_cur_groups
    groups_to_remove = set_cur_groups - set_new_groups

    for group_id in groups_to_add:
        user_group = UserGroup()
        user_group.user_id = user_id
        user_group.group_id = group_id
        db.session.add(user_group)

    for group in groups_to_remove:
        UserGroup.query.filter(
            UserGroup.user_id == user_id,
            UserGroup.group_id == group
        ).delete()

    db.session.commit()

    ac_auto_update_user_effective_access(user_id)


def update_user_orgs(user_id, orgs):
    cur_orgs = UserOrganisation.query.with_entities(
        UserOrganisation.org_id,
        UserOrganisation.is_primary_org
    ).filter(UserOrganisation.user_id == user_id).all()

    updated = False
    primary_org = 0
    for org in cur_orgs:
        if org.is_primary_org:
            primary_org = org.org_id

    if primary_org == 0:
        return False, 'User does not have primary organisation. Set one before managing its organisations'

    set_cur_orgs = set([org.org_id for org in cur_orgs])
    set_new_orgs = set(int(org) for org in orgs)

    orgs_to_add = set_new_orgs - set_cur_orgs
    orgs_to_remove = set_cur_orgs - set_new_orgs

    for org in orgs_to_add:
        user_org = UserOrganisation()
        user_org.user_id = user_id
        user_org.org_id = org
        db.session.add(user_org)
        updated = True

    for org in orgs_to_remove:
        if org != primary_org:
            UserOrganisation.query.filter(
                UserOrganisation.user_id == user_id,
                UserOrganisation.org_id == org
            ).delete()
        else:
            db.session.rollback()
            return False, f'Cannot delete user from primary organisation {org}. Change it before deleting.'
        updated = True

    db.session.commit()

    ac_auto_update_user_effective_access(user_id)
    return True, f'Organisations membership updated' if updated else "Nothing changed"


def add_user_to_organisation(user_id, org_id):

    exists = UserOrganisation.query.filter(
        UserOrganisation.user_id == user_id,
        UserOrganisation.org_id == org_id
    ).scalar()

    if exists:
        return True

    # Check if user has a primary org already
    prim_org = get_user_primary_org(user_id=user_id)

    uo = UserOrganisation()
    uo.user_id = user_id
    uo.org_id = org_id
    uo.is_primary_org = prim_org is None
    db.session.add(uo)
    db.session.commit()
    return True


def get_user_primary_org(user_id):

    uo = UserOrganisation.query.filter(
            and_(UserOrganisation.user_id == user_id,
                 UserOrganisation.is_primary_org == True)
    ).all()

    if not uo:
        return None

    index = 0
    if len(uo) > 1:
        # Fix potential duplication
        for u in uo:
            if index == 0:
                continue
            u.is_primary_org = False
        db.session.commit()

    return uo


def add_user_to_group(user_id, group_id):
    exists = UserGroup.query.filter(
        UserGroup.user_id == user_id,
        UserGroup.group_id == group_id
    ).scalar()

    if exists:
        return True

    ug = UserGroup()
    ug.user_id = user_id
    ug.group_id = group_id
    db.session.add(ug)
    db.session.commit()
    return True


def get_user_organisations(user_id):
    user_org = UserOrganisation.query.with_entities(
        Organisation.org_name,
        Organisation.org_id,
        Organisation.org_uuid,
        UserOrganisation.is_primary_org
    ).filter(
        UserOrganisation.user_id == user_id
    ).join(
        UserOrganisation.org
    ).all()

    output = []
    for org in user_org:
        output.append(org._asdict())

    return output


def get_user_cases_access(user_id):

    user_accesses = UserCaseAccess.query.with_entities(
        UserCaseAccess.access_level,
        UserCaseAccess.case_id,
        Cases.name.label('case_name')
    ).join(
        UserCaseAccess.case
    ).filter(
        UserCaseAccess.user_id == user_id
    ).all()

    user_cases_access = []
    for kuser in user_accesses:
        user_cases_access.append({
            "access_level": kuser.access_level,
            "access_level_list": ac_access_level_to_list(kuser.access_level),
            "case_id": kuser.case_id,
            "case_name": kuser.case_name
        })

    return user_cases_access


def remove_case_access_from_user(user_id, case_id):
    if not user_id or type(user_id) is not int:
        return

    if not case_id or type(case_id) is not int:
        return

    UserCaseAccess.query.filter(
        and_(
            UserCaseAccess.case_id == case_id,
            UserCaseAccess.user_id == user_id
        )).delete()

    db.session.commit()

    ac_auto_update_user_effective_access(user_id)
    return


def get_user_details(user_id):

    user = User.query.filter(User.id == user_id).first()

    if not user:
        return None

    row = {}
    row['user_id'] = user.id
    row['user_uuid'] = user.uuid
    row['user_name'] = user.name
    row['user_login'] = user.user
    row['user_email'] = user.email
    row['user_active'] = user.active

    row['user_groups'] = get_user_groups(user_id)
    row['user_organisations'] = get_user_organisations(user_id)
    row['user_permissions'] = get_user_effective_permissions(user_id)
    row['user_cases_access'] = get_user_cases_access(user_id)

    return row


def add_case_access_to_user(user, cases_list, access_level):
    if not user:
        return None, "Invalid user"

    for case_id in cases_list:
        case = get_case(case_id)
        if not case:
            return None, "Invalid case ID"

        access_level_mask = ac_access_level_mask_from_val_list([access_level])

        ocas = UserCaseAccess.query.filter(
            and_(
                UserCaseAccess.case_id == case_id,
                UserCaseAccess.user_id == user.id
            )).all()
        if ocas:
            for oca in ocas:
                db.session.delete(oca)

        oca = UserCaseAccess()
        oca.user_id = user.id
        oca.access_level = access_level_mask
        oca.case_id = case_id
        db.session.add(oca)

    db.session.commit()
    ac_auto_update_user_effective_access(user.id)

    return user, "Updated"


def get_user_by_username(username):
    user = User.query.filter(User.user == username).first()
    return user


def get_users_list():
    users = User.query.all()

    output = []
    for user in users:
        row = {}
        row['user_id'] = user.id
        row['user_uuid'] = user.uuid
        row['user_name'] = user.name
        row['user_login'] = user.user
        row['user_email'] = user.email
        row['user_active'] = user.active
        output.append(row)

    return output


def get_users_list_restricted():
    users = User.query.all()

    output = []
    for user in users:
        row = {}
        row['user_id'] = user.id
        row['user_uuid'] = user.uuid
        row['user_name'] = user.name
        row['user_login'] = user.user
        row['user_active'] = user.active
        output.append(row)

    return output


def create_user(user_name, user_login, user_password, user_email, user_isadmin, user_external_id: str = None):
    pw_hash = bc.generate_password_hash(user_password.encode('utf8')).decode('utf8')

    user = User(user_login, user_name, user_email, pw_hash, True, external_id=user_external_id)
    user.save()

    db.session.commit()
    return user


def update_user(user: User, name: str = None, email: str = None, password: str = None, user_isadmin: bool = None):

    if password is not None:
        pw_hash = bc.generate_password_hash(password.encode('utf8')).decode('utf8')
        user.password = pw_hash

    for key, value in [('name', name,), ('email', email,)]:
        if value is not None:
            setattr(user, key, value)

    db.session.commit()

    return user


def delete_user(user_id):
    UserCaseAccess.query.filter(UserCaseAccess.user_id == user_id).delete()
    UserOrganisation.query.filter(UserOrganisation.user_id == user_id).delete()
    UserGroup.query.filter(UserGroup.user_id == user_id).delete()
    UserCaseEffectiveAccess.query.filter(UserCaseEffectiveAccess.user_id == user_id).delete()

    User.query.filter(User.id == user_id).delete()
    db.session.commit()


def user_exists(user_name, user_email):
    user = User.query.filter_by(user=user_name).first()
    user_by_email = User.query.filter_by(email=user_email).first()

    return user or user_by_email

