from flask import session
from flask_login import current_user
from sqlalchemy import and_

import app
from app import db
from app.datamgmt.manage.manage_access_control_db import check_ua_case_client
from app.models import Cases, Client
from app.models.authorization import CaseAccessLevel, UserClient
from app.models.authorization import Group
from app.models.authorization import GroupCaseAccess
from app.models.authorization import Organisation
from app.models.authorization import OrganisationCaseAccess
from app.models.authorization import Permissions
from app.models.authorization import User
from app.models.authorization import UserCaseAccess
from app.models.authorization import UserCaseEffectiveAccess
from app.models.authorization import UserGroup
from app.models.authorization import UserOrganisation

log = app.app.logger


def ac_flag_match_mask(flag, mask):
    return (flag & mask) == mask


def ac_get_mask_full_permissions():
    """
    Return access mask for full permissions
    """
    am = 0
    for perm in Permissions._member_names_:
        am |= Permissions[perm].value

    return am


def get_auto_follow_groups():
    return UserGroup.query.with_entities(
        Group.group_auto_follow_access_level,
        Group.group_id,
        User.id
    ).join(
        UserGroup.user
    ).join(
        UserGroup.group
    ).filter(
        Group.group_auto_follow == True
    ).all()


def ac_combine_groups_access(groups_list):
    """
    Combine a list of group access masks
    """
    users = {}
    for group in groups_list:
        if group.id in users:
            if group.group_auto_follow_access_level > users[group.id]:
                users[group.id] = group.group_auto_follow_access_level

        else:
            users[group.id] = group.group_auto_follow_access_level

    return users


def ac_get_mask_analyst():
    """
    Return a standard access mask for analysts
    """
    return Permissions.standard_user.value | Permissions.alerts_read.value \
        | Permissions.alerts_write.value | Permissions.search_across_cases.value | Permissions.customers_read.value \
        | Permissions.activities_read.value


def ac_permission_to_list(permission):
    """
    Return a list of permissions from a permission mask
    """
    perms = []
    for perm in Permissions._member_names_:
        if permission & Permissions[perm].value:
            perms.append({
                'name': perm,
                'value': Permissions[perm].value
            })

    return perms


def ac_mask_from_val_list(permissions):
    """
    Return a permission mask from a list of permissions
    """
    am = 0
    for perm in permissions:
        am |= int(perm)

    return am


def ac_get_all_permissions():
    """
    Return a list of all permissions
    """
    perms = []
    for perm in Permissions._member_names_:
        perms.append({
            'name': perm,
            'value': Permissions[perm].value
        })

    return perms


def ac_get_detailed_effective_permissions_from_groups(groups):
    """
    Return a list of permissions from a list of groups
    """
    perms = {}
    for group in groups:
        perm = group.group_permissions

        for std_perm in Permissions._member_names_:

            if perm & Permissions[std_perm].value:
                if Permissions[std_perm].value not in perms:
                    perms[Permissions[std_perm].value] = {
                        'name': std_perm,
                        'value': Permissions[std_perm].value,
                        'inherited_from': [group.group_name]
                    }

                else:
                    if group.group_name not in perms[Permissions[std_perm].value]['inherited_from']:
                        perms[Permissions[std_perm].value]['inherited_from'].append(group.group_name)

    return perms


def ac_get_effective_permissions_from_groups(groups):
    """
    Return a permission mask from a list of groups
    """
    final_perm = 0
    for group in groups:
        final_perm &= group.group_permissions

    return final_perm


def ac_get_effective_permissions_of_user(user):
    """
    Return a permission mask from a user
    """

    groups_perms = UserGroup.query.with_entities(
        Group.group_permissions,
    ).filter(
        UserGroup.user_id == user.id
    ).join(
        UserGroup.group
    ).all()

    final_perm = 0
    for group in groups_perms:
        final_perm |= group.group_permissions

    return final_perm


def ac_ldp_group_removal(user_id, group_id):
    """
    Access control lockdown prevention on group removal
    """
    if current_user.id != user_id:
        return False

    groups_perms = UserGroup.query.with_entities(
        Group.group_permissions,
        Group.group_name,
        Group.group_id,
        Group.group_uuid
    ).filter(
        UserGroup.user_id == user_id
    ).join(
        UserGroup.group
    ).all()

    adm_access_count = []

    for group in groups_perms:
        perm = group.group_permissions
        if ac_flag_match_mask(perm,
                              Permissions.server_administrator.value):
            adm_access_count.append(group.group_id)

    if len(adm_access_count) == 1 and adm_access_count[0] == group_id:
        return True

    return False


def ac_ldp_group_update(user_id):
    """
    Access control lockdown prevention on group update
    """
    if current_user.id != user_id:
        return False

    groups_perms = UserGroup.query.with_entities(
        Group.group_permissions,
        Group.group_name,
        Group.group_id,
        Group.group_uuid
    ).filter(
        UserGroup.user_id == user_id
    ).join(
        UserGroup.group
    ).all()

    adm_access_count = []

    for group in groups_perms:
        perm = group.group_permissions
        if ac_flag_match_mask(perm,
                              Permissions.server_administrator.value):
            adm_access_count.append(group.group_id)

    if len(adm_access_count) == 0:
        return True

    return False


def ac_trace_effective_user_permissions(user_id):
    """
    Returns a detailed permission list from a user
    """
    groups_perms = UserGroup.query.with_entities(
        Group.group_permissions,
        Group.group_name,
        Group.group_id,
        Group.group_uuid
    ).filter(
        UserGroup.user_id == user_id
    ).join(
        UserGroup.group
    ).all()

    perms = {
        'details': {},
        'effective': 0,
    }

    for group in groups_perms:
        perm = group.group_permissions
        perms['effective'] |= group.group_permissions

        for std_perm in Permissions._member_names_:

            if ac_flag_match_mask(perm, Permissions[std_perm].value):
                if Permissions[std_perm].value not in perms['details']:
                    perms['details'][Permissions[std_perm].value] = {
                        'name': std_perm,
                        'value': Permissions[std_perm].value,
                        'inherited_from': {
                            group.group_id: {
                                'group_name': group.group_name,
                                'group_uuid': group.group_uuid
                            }

                        }
                    }
                else:
                    if group.group_name not in perms['details'][Permissions[std_perm].value]['inherited_from']:
                        perms['details'][Permissions[std_perm].value]['inherited_from'].update({
                            group.group_id: {
                                'group_name': group.group_name,
                                'group_uuid': group.group_uuid
                            }
                        })

    return perms


def ac_fast_check_user_has_case_access(user_id, cid, access_level):
    """
    Returns true if the user has access to the case
    """
    ucea = UserCaseEffectiveAccess.query.with_entities(
        UserCaseEffectiveAccess.access_level
    ).filter(
        UserCaseEffectiveAccess.user_id == user_id,
        UserCaseEffectiveAccess.case_id == cid
    ).first()

    if not ucea:
        # The user has no direct access, check if he is part of the client
        cuacu = check_ua_case_client(user_id, cid)
        if cuacu is None:
            return None
        ac_set_case_access_for_user(user_id, cid, cuacu.access_level)

        return cuacu.access_level

    if ac_flag_match_mask(ucea[0], CaseAccessLevel.deny_all.value):
        return None

    for acl in access_level:
        if ac_flag_match_mask(ucea[0], acl.value):
            return ucea[0]

    return None


def ac_fast_check_current_user_has_case_access(cid, access_level):
    return ac_fast_check_user_has_case_access(current_user.id, cid, access_level)


def ac_recompute_effective_ac_from_users_list(users_list):
    """
    Recompute all users effective access of users
    """
    for member in users_list:
        ac_auto_update_user_effective_access(user_id=member['id'])

    return


def ac_recompute_all_users_effective_ac():
    """
    Recompute all users effective access
    """
    users = User.query.with_entities(
        User.id
    ).all()
    for user_id in users:
        ac_auto_update_user_effective_access(user_id[0])

    return


def ac_recompute_effective_ac(user_id):
    """
    Recompute a users effective access
    """

    return ac_auto_update_user_effective_access(user_id)


def ac_add_users_multi_effective_access(users_list, cases_list, access_level):
    """
    Add multiple users to multiple cases with a specific access level
    """
    for case_id in cases_list:
        ac_add_user_effective_access(users_list, case_id=case_id, access_level=access_level)

    return


def ac_add_user_effective_access(users_list, case_id, access_level):
    """
    Directly add a set of effective user access
    """

    UserCaseEffectiveAccess.query.filter(
        UserCaseEffectiveAccess.case_id == case_id,
        UserCaseEffectiveAccess.user_id.in_(users_list)
    ).delete()

    access_to_add = []
    for user_id in users_list:
        ucea = UserCaseEffectiveAccess()
        ucea.user_id = user_id
        ucea.case_id = case_id
        ucea.access_level = access_level
        access_to_add.append(ucea)

    db.session.add_all(access_to_add)
    db.session.commit()


def ac_add_user_effective_access_from_map(users_map, case_id):
    """
    Directly add a set of effective user access
    """
    UserCaseEffectiveAccess.query.filter(
        UserCaseEffectiveAccess.case_id == case_id,
        UserCaseEffectiveAccess.user_id.in_(users_map.keys())
    ).delete()

    access_to_add = []
    for user_id in users_map:
        ucea = UserCaseEffectiveAccess()
        ucea.user_id = user_id
        ucea.case_id = case_id
        ucea.access_level = users_map[user_id]
        access_to_add.append(ucea)

    db.session.add_all(access_to_add)
    db.session.commit()


def ac_set_new_case_access(org_members, case_id, customer_id = None):
    """
    Set a new case access
    """

    users = ac_apply_autofollow_groups_access(case_id)
    if current_user.id in users.keys():
        del users[current_user.id]

    users_full = User.query.with_entities(User.id).all()
    users_full_access = list(set([u.id for u in users_full]) - set(users.keys()))

    # Default users case access - Full access
    ac_add_user_effective_access(users_full_access, case_id, CaseAccessLevel.deny_all.value)

    # Add specific right for the user creating the case
    UserCaseAccess.query.filter(
        UserCaseAccess.case_id == case_id,
        UserCaseAccess.user_id == current_user.id
    ).delete()
    db.session.commit()
    uca = UserCaseAccess()
    uca.case_id = case_id
    uca.user_id = current_user.id
    uca.access_level = CaseAccessLevel.full_access.value
    db.session.add(uca)
    db.session.commit()

    ac_add_user_effective_access([current_user.id], case_id, CaseAccessLevel.full_access.value)

    # Add customer permissions for all users belonging to the customer
    if customer_id:
        users_client = UserClient.query.filter(
            UserClient.client_id == customer_id
        ).with_entities(
            UserClient.user_id,
            UserClient.access_level
        ).all()
        users_map = { u.user_id: u.access_level for u in users_client }
        ac_add_user_effective_access_from_map(users_map, case_id)


def ac_apply_autofollow_groups_access(case_id):
    """
    Apply a direct effective user access to users within a group
    """

    groups = get_auto_follow_groups()
    users = ac_combine_groups_access(groups)

    rows_to_push = []
    for user_id in users:
        ucea = UserCaseEffectiveAccess()
        ucea.user_id = user_id
        ucea.case_id = case_id
        ucea.access_level = users[user_id]
        rows_to_push.append(ucea)

    grps_to_add = {}
    for group in groups:
        if group.group_id not in grps_to_add:
            grps_to_add[group.group_id] = group.group_auto_follow_access_level

    for group_id in grps_to_add:
        gca = GroupCaseAccess()
        gca.case_id = case_id
        gca.group_id = group_id
        gca.access_level = grps_to_add[group_id]
        rows_to_push.append(gca)

    db.session.add_all(rows_to_push)
    db.session.commit()
    return users


def ac_auto_update_user_effective_access(user_id):
    """
    Updates the effective access of a user given its ID
    """
    uceas = UserCaseEffectiveAccess.query.filter(
        UserCaseEffectiveAccess.user_id == user_id
    ).all()

    grouped_uca = {}
    for ucea in uceas:
        grouped_uca[ucea.case_id] = ucea.access_level

    target_ucas = ac_get_user_cases_access(user_id)

    ucea_to_add = {}
    cid_to_remove = []

    for case_id in target_ucas:
        if case_id not in grouped_uca:
            ucea_to_add.update({case_id: target_ucas[case_id]})
        else:
            if not ac_flag_match_mask(grouped_uca[case_id], target_ucas[case_id]):
                cid_to_remove.append(case_id)
                ucea_to_add.update({case_id: target_ucas[case_id]})

    for prev_case_id in grouped_uca:
        if prev_case_id not in target_ucas.keys():
            cid_to_remove.append(prev_case_id)

    UserCaseEffectiveAccess.query.where(and_(
        UserCaseEffectiveAccess.user_id == user_id,
        UserCaseEffectiveAccess.case_id.in_(cid_to_remove)
    )).delete()

    for case_id in ucea_to_add:
        ucea = UserCaseEffectiveAccess()
        ucea.user_id = user_id
        ucea.case_id = case_id
        ucea.access_level = ucea_to_add[case_id]
        db.session.add(ucea)

    db.session.commit()

    return


def ac_remove_case_access_from_user(user_id, case_id):
    """
    Remove a case access from a user
    """

    uac = UserCaseEffectiveAccess.query.where(and_(
        UserCaseEffectiveAccess.user_id == user_id,
        UserCaseEffectiveAccess.case_id == case_id
    )).all()

    if len(uac) > 1:
        log.error(f'Multiple access found for user {user_id} and case {case_id}')
        for u in uac:
            db.session.delete(u)
        db.session.commit()

        uac = UserCaseEffectiveAccess()
        uac.user_id = user_id
        uac.case_id = case_id
        uac.access_level = CaseAccessLevel.deny_all.value
        db.session.add(uac)

    elif len(uac) == 1:
        uac = uac[0]
        uac.access_level = CaseAccessLevel.deny_all.value

    db.session.commit()

    return


def ac_set_case_access_for_users(users, case_id, access_level):
    """
    Set a case access for a list of users
    """
    logs = "Access updated"

    for user in users:
        user_id = user.get('id')
        if user_id == current_user.id:
            logs = "It's done, but I excluded you from the list of users to update, Dave"
            ac_set_case_access_for_user(user.get('id'), case_id, access_level=CaseAccessLevel.full_access.value)
            continue

        ac_set_case_access_for_user(user.get('id'), case_id, access_level)

    db.session.commit()
    return True, logs


def ac_set_case_access_for_user(user_id, case_id, access_level, commit=True):
    """
    Set a case access from a user
    """

    uac = UserCaseEffectiveAccess.query.where(and_(
        UserCaseEffectiveAccess.user_id == user_id,
        UserCaseEffectiveAccess.case_id == case_id
    )).all()

    if len(uac) > 1:
        log.error(f'Multiple access found for user {user_id} and case {case_id}')
        for u in uac:
            db.session.delete(u)
        db.session.commit()

        uac = UserCaseEffectiveAccess()
        uac.user_id = user_id
        uac.case_id = case_id
        uac.access_level = access_level
        db.session.add(uac)

    elif len(uac) == 1:
        uac = uac[0]
        uac.access_level = access_level

    if commit:
        db.session.commit()

    return


def ac_get_fast_user_cases_access(user_id):
    ucea = UserCaseEffectiveAccess.query.with_entities(
        UserCaseEffectiveAccess.case_id
    ).filter(and_(
        UserCaseEffectiveAccess.user_id == user_id,
        UserCaseEffectiveAccess.access_level != CaseAccessLevel.deny_all.value
    )).all()

    return [e.case_id for e in ucea]


def ac_get_user_case_counts(user_id):
    query = UserCaseEffectiveAccess.query.filter(
        UserCaseEffectiveAccess.user_id == user_id,
        UserCaseEffectiveAccess.access_level != CaseAccessLevel.deny_all.value
    )

    ucea_count = query.count()
    open_cases_count = query.join(Cases).filter(Cases.close_date == None).count()
    owned_cases_count = query.join(
        Cases, isouter=True
    ).filter(
        and_(
            Cases.owner_id == user_id,
            Cases.close_date == None
        )
    ).count()

    return ucea_count, open_cases_count, owned_cases_count


def ac_get_user_cases_access(user_id):
    # ocas = OrganisationCaseAccess.query.with_entities(
    #     Cases.case_id,
    #     OrganisationCaseAccess.access_level
    # ).filter(
    #     and_(UserOrganisation.user_id == user_id,
    #          OrganisationCaseAccess.org_id == UserOrganisation.org_id)
    # ).join(
    #     OrganisationCaseAccess.case,
    # ).all()
    cases = Cases.query.with_entities(
        Cases.case_id
    ).all()

    gcas = GroupCaseAccess.query.with_entities(
        Cases.case_id,
        GroupCaseAccess.access_level
    ).filter(
        and_(UserGroup.user_id == user_id,
             UserGroup.group_id == GroupCaseAccess.group_id)
    ).join(
        GroupCaseAccess.case
    ).all()

    ccas = UserClient.query.with_entities(
        UserClient.access_level,
        Cases.case_id,
    ).join(
        Cases, UserClient.client_id == Cases.client_id
    ).filter(
        UserClient.user_id == user_id
    ).all()

    ucas = UserCaseAccess.query.with_entities(
        Cases.case_id,
        UserCaseAccess.access_level
    ).filter(
        and_(UserCaseAccess.user_id == user_id)
    ).join(
        UserCaseAccess.case
    ).all()

    effective_cases_access = {}
    for oca in cases:
        effective_cases_access[oca.case_id] = CaseAccessLevel.deny_all.value

    for gca in gcas:
        effective_cases_access[gca.case_id] = gca.access_level

    for cca in ccas:
        effective_cases_access[cca.case_id] = cca.access_level

    for uca in ucas:
        effective_cases_access[uca.case_id] = uca.access_level

    return effective_cases_access


def ac_trace_user_effective_cases_access_2(user_id):

    gcas = GroupCaseAccess.query.with_entities(
        Group.group_name,
        Group.group_id,
        Group.group_uuid,
        Cases.case_id,
        Cases.name,
        GroupCaseAccess.access_level
    ).filter(
        and_(UserGroup.user_id == user_id,
             UserGroup.group_id == GroupCaseAccess.group_id)
    ).join(
        GroupCaseAccess.case
    ).join(
        GroupCaseAccess.group
    ).all()

    ucas = UserCaseAccess.query.with_entities(
        User.name.label('user_name'),
        User.id.label('user_id'),
        User.uuid.label('user_uuid'),
        Cases.case_id,
        Cases.name,
        UserCaseAccess.access_level
    ).filter(
        and_(UserCaseAccess.user_id == user_id)
    ).join(
        UserCaseAccess.case
    ).join(
        UserCaseAccess.user
    ).all()

    effective_cases_access = {}
    cases = Cases.query.with_entities(
        Cases.case_id,
        Cases.name
    ).all()

    ccas = UserClient.query.with_entities(
        UserClient.access_level,
        Cases.case_id,
        Cases.name.label('case_name'),
        Client.name.label('client_name'),
        Client.client_id,
        Client.client_uuid
    ).join(
        Cases, UserClient.client_id == Cases.client_id
    ).join(
        Client, Client.client_id == Cases.client_id
    ).filter(
        UserClient.user_id == user_id
    ).all()

    # Organisation case access. Default access level
    for oca in cases:
        access = {
            'state': 'Effective',
            'access_list': CaseAccessLevel.deny_all.name,
            'access_value': CaseAccessLevel.deny_all.value,
            'inherited_from': {
                'object_type': 'default_access_level',
                'object_name': 'Default access level',
                'object_id': '',
                'object_uuid': ''
            }
        }

        effective_cases_access[oca.case_id] = {
            'case_info': {
                'case_name': oca.name,
                'case_id': oca.case_id
            },
            'user_access': [],
            'user_effective_access': CaseAccessLevel.deny_all.value
        }

        effective_cases_access[oca.case_id]['user_access'].append(access)

    # Group case access
    for gca in gcas:
        access = {
            'state': 'Effective',
            'access_list': ac_access_level_to_list(gca.access_level),
            'access_value': gca.access_level,
            'inherited_from': {
                'object_type': 'group_access_level',
                'object_name': gca.group_name,
                'object_id': gca.group_id,
                'object_uuid': gca.group_uuid
            }
        }

        if gca.case_id in effective_cases_access:
            effective_cases_access[gca.case_id]['user_effective_access'] = gca.access_level
            for kec in effective_cases_access[gca.case_id]['user_access']:
                kec['state'] = f'Overwritten by group {gca.group_name}'

        else:
            effective_cases_access[gca.case_id] = {
                'case_info': {
                    'case_name': gca.name,
                    'case_id': gca.case_id
                },
                'user_access': [],
                'user_effective_access': gca.access_level
            }

        effective_cases_access[gca.case_id]['user_access'].append(access)

    # Client case access:
    for cca in ccas:
        access = {
            'state': 'Effective',
            'access_list': ac_access_level_to_list(cca.access_level),
            'access_value': cca.access_level,
            'inherited_from': {
                'object_type': 'customer_access_level',
                'object_name': cca.client_name,
                'object_id': cca.client_id,
                'object_uuid': cca.client_uuid
            }
        }

        if cca.case_id in effective_cases_access:
            effective_cases_access[cca.case_id]['user_effective_access'] = cca.access_level
            for kec in effective_cases_access[cca.case_id]['user_access']:
                kec['state'] = f'Overwritten by customer {cca.client_name}'

        else:
            effective_cases_access[cca.case_id] = {
                'case_info': {
                    'case_name': cca.case_name,
                    'case_id': cca.case_id
                },
                'user_access': [],
                'user_effective_access': cca.access_level
            }

        effective_cases_access[cca.case_id]['user_access'].append(access)

    # User case access
    for uca in ucas:
        access = {
            'state': 'Effective',
            'access_list': ac_access_level_to_list(uca.access_level),
            'access_value': uca.access_level,
            'inherited_from': {
                'object_type': 'user_access_level',
                'object_name': uca.user_name,
                'object_id': uca.user_id,
                'object_uuid': uca.user_uuid
            }
        }

        if uca.case_id in effective_cases_access:
            effective_cases_access[uca.case_id]['user_effective_access'] = uca.access_level

            for kec in effective_cases_access[uca.case_id]['user_access']:
                kec['state'] = f'Overwritten by self user access'

        else:
            effective_cases_access[uca.case_id] = {
                'case_info': {
                    'case_name': uca.name,
                    'case_id': uca.case_id
                },
                'user_access': [],
                'user_effective_access': uca.access_level
            }

        effective_cases_access[uca.case_id]['user_access'].append(access)

    for case_id in effective_cases_access:
        effective_cases_access[case_id]['user_effective_access'] = ac_access_level_to_list(
            effective_cases_access[case_id]['user_effective_access'])

    return effective_cases_access


def ac_trace_case_access(case_id):

    case = Cases.query.with_entities(
        Cases.case_id,
        Cases.name
    ).filter(
        Cases.case_id == case_id
    ).first()

    if not case:
        return {}

    ocas = OrganisationCaseAccess.query.with_entities(
        Organisation.org_name,
        Organisation.org_id,
        Organisation.org_uuid,
        OrganisationCaseAccess.access_level,
        User.id.label('user_id'),
        User.name.label('user_name'),
        User.email.label('user_email'),
        User.uuid.label('user_uuid')
    ).filter(
        and_(OrganisationCaseAccess.case_id == case.case_id,
             OrganisationCaseAccess.org_id == UserOrganisation.org_id)
    ).join(
        OrganisationCaseAccess.org,
        UserOrganisation.user
    ).all()

    gcas = GroupCaseAccess.query.with_entities(
        Group.group_name,
        Group.group_id,
        Group.group_uuid,
        GroupCaseAccess.access_level,
        User.id.label('user_id'),
        User.name.label('user_name'),
        User.email.label('user_email'),
        User.uuid.label('user_uuid')
    ).filter(
        and_(GroupCaseAccess.case_id == case.case_id,
             UserGroup.group_id == GroupCaseAccess.group_id)
    ).join(
        GroupCaseAccess.group,
        UserGroup.user
    ).all()

    ucas = UserCaseAccess.query.with_entities(
        User.id.label('user_id'),
        User.name.label('user_name'),
        User.uuid.label('user_uuid'),
        User.email.label('user_email'),
        UserCaseAccess.access_level
    ).filter(
        and_(UserCaseAccess.case_id == case.case_id)
    ).join(
        UserCaseAccess.user
    ).all()

    case_access = {}

    for uca in ucas:
        user = {
            'access_trace': [],
            'user_effective_access': 0,
            'user_effective_access_list': [],
            'user_info': {
                'user_name': uca.user_name,
                'user_uuid': uca.user_uuid,
                'user_email': uca.user_email
            }
        }
        for ac_l in CaseAccessLevel:

            if uca:
                if ac_flag_match_mask(uca.access_level, ac_l.value):
                    user['user_effective_access'] |= uca.access_level
                    user['access_trace'].append({
                        'state': 'Effective',
                        'name': ac_l.name,
                        'value': ac_l.value,
                        'inherited_from': {
                            'object_type': 'user_access_level',
                            'object_name': 'self',
                            'object_id': 'self',
                            'object_uuid': 'self'
                        }
                    })
                    user['user_effective_access_list'].append(ac_l.name)
                    has_uca_overwritten = True
                    if ac_l.value == CaseAccessLevel.deny_all.value:
                        has_uca_deny_all = True

        if uca.user_id not in case_access:
            case_access.update({
                uca.user_id: user
            })

    for gca in gcas:
        if gca.user_id not in case_access:
            user = {
                'access_trace': [],
                'user_effective_access': 0,
                'user_effective_access_list': [],
                'user_info': {
                    'user_name': gca.user_name,
                    'user_uuid': gca.user_uuid,
                    'user_email': gca.user_email
                }
            }
        else:
            user = case_access[gca.user_id]

        for ac_l in CaseAccessLevel:

            if gca:
                if ac_flag_match_mask(gca.access_level, ac_l.value):
                    if gca.user_id not in case_access:
                        user['user_effective_access'] |= gca.access_level
                        user['user_effective_access_list'].append(ac_l.name)
                        state = 'Effective'
                    else:
                        state = 'Overwritten by user access'

                    user['access_trace'].append({
                            'state': state,
                            'name': ac_l.name,
                            'value': ac_l.value,
                            'inherited_from': {
                                'object_type': 'group_access_level',
                                'object_name': gca.group_name,
                                'object_id': gca.group_id,
                                'object_uuid': gca.group_uuid
                            }
                        })

        if gca.user_id not in case_access:
            case_access.update({
                gca.user_id: user
            })

    for oca in ocas:
        if oca.user_id not in case_access:
            user = {
                'access_trace': [],
                'user_effective_access': 0,
                'user_effective_access_list': [],
                'user_info': {
                    'user_name': oca.user_name,
                    'user_uuid': oca.user_uuid,
                    'user_email': oca.user_email
                }
            }
        else:
            user = case_access[oca.user_id]

        for ac_l in CaseAccessLevel:

            if oca:
                if ac_flag_match_mask(oca.access_level, ac_l.value):
                    if oca.user_id not in case_access:
                        user['user_effective_access'] |= oca.access_level
                        user['user_effective_access_list'].append(ac_l.name)
                        state = 'Effective'
                    else:
                        state = 'Overwritten by user or group access'

                    user['access_trace'].append({
                            'state': state,
                            'name': ac_l.name,
                            'value': ac_l.value,
                            'inherited_from': {
                                'object_type': 'organisation_access_level',
                                'object_name': oca.org_name,
                                'object_id': oca.org_id,
                                'object_uuid': oca.org_uuid
                            }
                        })

        if oca.user_id not in case_access:
            case_access.update({
                oca.user_id: user
            })

    return case_access


def ac_get_mask_case_access_level_full():
    """
    Return a mask for full access level
    """
    am = 0
    for ac in CaseAccessLevel._member_names_:
        if CaseAccessLevel.deny_all.name == CaseAccessLevel[ac].name:
            continue

        am |= CaseAccessLevel[ac].value

    return am


def ac_get_all_access_level():
    """
    Return a list of all access levels
    """
    ac_list = []
    for ac in CaseAccessLevel._member_names_:
        ac_list.append({
            'name': ac,
            'value': CaseAccessLevel[ac].value
        })

    return ac_list


def ac_access_level_to_list(access_level):
    """
    Return a list of access level from  an access level mask
    """
    access_levels = []
    for ac in CaseAccessLevel._member_names_:
        if ac_flag_match_mask(access_level, CaseAccessLevel[ac].value):
            access_levels.append({
                'name': ac,
                'value': CaseAccessLevel[ac].value
            })

    return access_levels


def ac_access_level_mask_from_val_list(access_levels):
    """
    Return an access level mask from a list of access levels
    """
    am = 0
    for acc in access_levels:
        am |= int(acc)

    return am


def ac_user_has_permission(user, permission):
    """
    Return True if user has permission
    """
    return ac_flag_match_mask(ac_get_effective_permissions_of_user(user), permission.value)


def ac_current_user_has_permission(permission):
    """
    Return True if current user has permission
    """
    return ac_flag_match_mask(session['permissions'], permission.value)