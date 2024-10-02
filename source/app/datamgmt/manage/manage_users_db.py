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
from typing import List

from functools import reduce
from flask_login import current_user
from sqlalchemy import and_, desc, asc

import app
from app import bc
from app import db
from app.datamgmt.case.case_db import get_case
from app.iris_engine.access_control.utils import ac_access_level_mask_from_val_list, ac_ldp_group_removal
from app.iris_engine.access_control.utils import ac_access_level_to_list
from app.iris_engine.access_control.utils import ac_auto_update_user_effective_access
from app.iris_engine.access_control.utils import ac_get_detailed_effective_permissions_from_groups
from app.iris_engine.access_control.utils import ac_remove_case_access_from_user
from app.iris_engine.access_control.utils import ac_set_case_access_for_user
from app.models import Cases, Client
from app.models.authorization import CaseAccessLevel, UserClient
from app.models.authorization import Group
from app.models.authorization import Organisation
from app.models.authorization import User
from app.models.authorization import UserCaseAccess
from app.models.authorization import UserCaseEffectiveAccess
from app.models.authorization import UserGroup
from app.models.authorization import UserOrganisation


def get_user(user_id, id_key: str = 'id') -> [User, None]:
    user = User.query.filter(getattr(User, id_key) == user_id).first()
    return user


def get_active_user(user_id, id_key: str = 'id') -> [User, None]:
    user = User.query.filter(
        and_(
            getattr(User, id_key) == user_id,
            User.active == True
        )).first()
    return user


def get_active_user_by_login(username):
    return get_active_user(user_id=username, id_key='user')


def list_users_id():
    users = User.query.with_entities(User.user_id).all()
    return users


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

    for group_id in groups_to_remove:
        if current_user.id == user_id and ac_ldp_group_removal(user_id=user_id, group_id=group_id):
            continue

        UserGroup.query.filter(
            UserGroup.user_id == user_id,
            UserGroup.group_id == group_id
        ).delete()

    db.session.commit()

    ac_auto_update_user_effective_access(user_id)

def add_user_to_customer(user_id, customer_id):
    user_client = UserClient.query.filter(
        UserClient.user_id == user_id,
        UserClient.client_id == customer_id
    ).first()

    if user_client:
        return True

    user_client = UserClient()
    user_client.user_id = user_id
    user_client.client_id = customer_id
    user_client.access_level = CaseAccessLevel.full_access.value
    user_client.allow_alerts = True
    db.session.add(user_client)
    db.session.commit()

    ac_auto_update_user_effective_access(user_id)

    return True


def update_user_customers(user_id, customers):
    # Update the user's customers directly
    cur_customers = UserClient.query.with_entities(
        UserClient.client_id
    ).filter(UserClient.user_id == user_id).all()

    set_cur_customers = set([cust[0] for cust in cur_customers])
    set_new_customers = set(int(cust) for cust in customers)

    customers_to_add = set_new_customers - set_cur_customers
    customers_to_remove = set_cur_customers - set_new_customers

    for client_id in customers_to_add:
        user_client = UserClient()
        user_client.user_id = user_id
        user_client.client_id = client_id
        user_client.access_level = CaseAccessLevel.full_access.value
        user_client.allow_alerts = True
        db.session.add(user_client)

    for client_id in customers_to_remove:
        UserClient.query.filter(
            UserClient.user_id == user_id,
            UserClient.client_id == client_id
        ).delete()

    ac_auto_update_user_effective_access(user_id)

    db.session.commit()


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


def change_user_primary_org(user_id, old_org_id, new_org_id):

    uo_old = UserOrganisation.query.filter(
        UserOrganisation.user_id == user_id,
        UserOrganisation.org_id == old_org_id
    ).first()

    uo_new = UserOrganisation.query.filter(
        UserOrganisation.user_id == user_id,
        UserOrganisation.org_id == new_org_id
    ).first()

    if uo_old:
        uo_old.is_primary_org = False

    if not uo_new:
        uo = UserOrganisation()
        uo.user_id = user_id
        uo.org_id = new_org_id
        uo.is_primary_org = True
        db.session.add(uo)

    else:
        uo_new.is_primary_org = True

    db.session.commit()
    return


def add_user_to_organisation(user_id, org_id, make_primary=False):
    org_id = Organisation.query.first().org_id

    uo_exists = UserOrganisation.query.filter(
        UserOrganisation.user_id == user_id,
        UserOrganisation.org_id == org_id
    ).first()

    if uo_exists:
        uo_exists.is_primary_org = make_primary
        db.session.commit()

        return True

    # Check if user has a primary org already
    prim_org = get_user_primary_org(user_id=user_id)

    if make_primary:
        prim_org.is_primary_org = False
        db.session.commit()

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

    uoe = None
    index = 0
    if len(uo) > 1:
        # Fix potential duplication
        for u in uo:
            if index == 0:
                uoe = u
                continue
            u.is_primary_org = False
        db.session.commit()
    else:
        uoe = uo[0]

    return uoe


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


def get_user_clients(user_id: int) -> List[Client]:
    clients = UserClient.query.filter(
        UserClient.user_id == user_id
    ).join(
        UserClient.client
    ).with_entities(
        Client.client_id.label('customer_id'),
        Client.client_uuid,
        Client.name.label('customer_name')
    ).all()

    clients_out = [c._asdict() for c in clients]

    return clients_out


def get_user_cases_fast(user_id):

    user_cases = UserCaseEffectiveAccess.query.with_entities(
        UserCaseEffectiveAccess.case_id
    ).where(
        UserCaseEffectiveAccess.user_id == user_id,
        UserCaseEffectiveAccess.access_level != CaseAccessLevel.deny_all.value
    ).all()

    return [c.case_id for c  in user_cases]


def remove_cases_access_from_user(user_id, cases_list):
    if not user_id or type(user_id) is not int:
        return False, 'Invalid user id'

    if not cases_list or type(cases_list[0]) is not int:
        return False, "Invalid cases list"

    UserCaseAccess.query.filter(
        and_(
            UserCaseAccess.case_id.in_(cases_list),
            UserCaseAccess.user_id == user_id
        )).delete()

    db.session.commit()

    ac_auto_update_user_effective_access(user_id)
    return True, 'Cases access removed'


def remove_case_access_from_user(user_id, case_id):
    if not user_id or type(user_id) is not int:
        return False, 'Invalid user id'

    if not case_id or type(case_id) is not int:
        return False, "Invalid case id"

    UserCaseAccess.query.filter(
        and_(
            UserCaseAccess.case_id == case_id,
            UserCaseAccess.user_id == user_id
        )).delete()

    db.session.commit()

    ac_remove_case_access_from_user(user_id, case_id)
    return True, 'Case access removed'


def set_user_case_access(user_id, case_id, access_level):
    if user_id is None or type(user_id) is not int:
        return False, 'Invalid user id'

    if case_id is None or type(case_id) is not int:
        return False, "Invalid case id"

    if access_level is None or type(access_level) is not int:
        return False, "Invalid access level"

    if CaseAccessLevel.has_value(access_level) is False:
        return False, "Invalid access level"

    uca = UserCaseAccess.query.filter(
        UserCaseAccess.user_id == user_id,
        UserCaseAccess.case_id == case_id
    ).all()

    if len(uca) > 1:
        for u in uca:
            db.session.delete(u)
        db.session.commit()
        uca = None

    if not uca:
        uca = UserCaseAccess()
        uca.user_id = user_id
        uca.case_id = case_id
        uca.access_level = access_level
        db.session.add(uca)
    else:
        uca[0].access_level = access_level

    db.session.commit()

    ac_set_case_access_for_user(user_id, case_id, access_level)

    return True, 'Case access set to {} for user {}'.format(access_level, user_id)


def get_user_details(user_id, include_api_key=False):

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
    row['user_is_service_account'] = user.is_service_account

    if include_api_key:
        row['user_api_key'] = user.api_key

    row['user_groups'] = get_user_groups(user_id)
    row['user_organisations'] = get_user_organisations(user_id)
    row['user_permissions'] = get_user_effective_permissions(user_id)
    row['user_cases_access'] = get_user_cases_access(user_id)
    row['user_customers'] = get_user_clients(user_id)

    upg = get_user_primary_org(user_id)
    row['user_primary_organisation_id'] = upg.org_id if upg else 0

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
        row['user_is_service_account'] = user.is_service_account
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


def get_users_view_from_user_id(user_id):
    organisations = get_user_organisations(user_id)
    orgs_id = [uo.get('org_id') for uo in organisations]

    users = UserOrganisation.query.with_entities(
        User
    ).filter(and_(
        UserOrganisation.org_id.in_(orgs_id),
        UserOrganisation.user_id != user_id
    )).join(
        UserOrganisation.user
    ).all()

    return users


def get_users_id_view_from_user_id(user_id):
    organisations = get_user_organisations(user_id)
    orgs_id = [uo.get('org_id') for uo in organisations]

    users = UserOrganisation.query.with_entities(
        User.id
    ).filter(and_(
        UserOrganisation.org_id.in_(orgs_id),
        UserOrganisation.user_id != user_id
    )).join(
        UserOrganisation.user
    ).all()

    users = [u[0] for u in users]

    return users


def get_users_list_user_view(user_id):
    users = get_users_view_from_user_id(user_id)
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


def get_users_list_restricted_user_view(user_id):
    users = get_users_view_from_user_id(user_id)

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


def get_users_list_restricted_from_case(case_id):

    users = UserCaseEffectiveAccess.query.with_entities(
        User.id.label('user_id'),
        User.uuid.label('user_uuid'),
        User.name.label('user_name'),
        User.user.label('user_login'),
        User.active.label('user_active'),
        User.email.label('user_email'),
        UserCaseEffectiveAccess.access_level.label('user_access_level')
    ).filter(
        UserCaseEffectiveAccess.case_id == case_id
    ).join(
        UserCaseEffectiveAccess.user
    ).all()

    return [u._asdict() for u in users]


def create_user(user_name: str, user_login: str, user_password: str, user_email: str, user_active: bool,
                user_external_id: str = None, user_is_service_account: bool = False):

    if user_is_service_account is True and (user_password is None or user_password == ''):
        pw_hash = None

    else:
        pw_hash = bc.generate_password_hash(user_password.encode('utf8')).decode('utf8')

    user = User(user=user_login, name=user_name, email=user_email, password=pw_hash, active=user_active,
                external_id=user_external_id, is_service_account=user_is_service_account)
    user.save()

    add_user_to_organisation(user.id, org_id=1)
    ac_auto_update_user_effective_access(user_id=user.id)

    return user


def update_user(user: User, name: str = None, email: str = None, password: str = None):

    if password is not None and password != '':
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


def get_filtered_users(user_ids: str = None,
                       user_name: str = None,
                       user_login: str = None,
                       customer_id: int = None,
                       page: int = None,
                       per_page: int = None,
                       sort: str =None):
    """

    """
    conditions = []

    if user_ids is not None:
        conditions.append(User.id.in_(user_ids))

    if user_name is not None:
        conditions.append(User.name.ilike(user_name))

    if user_login is not None:
        conditions.append(User.user.ilike(user_login))

    if customer_id is not None:
        conditions.append(UserClient.client_id == customer_id)
        conditions.append(UserClient.user_id == User.id)

    if len(conditions) > 1:
        conditions = [reduce(and_, conditions)]

    order_func = desc if sort == 'desc' else asc

    try:

        filtered_users = db.session.query(
            User
        ).filter(
            *conditions
        ).order_by(
            order_func(User.id)
        ).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

    except Exception as e:
        app.logger.exception(f'Error getting users: {str(e)}')
        return None

    return filtered_users
