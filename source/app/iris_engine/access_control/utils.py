from flask import session
from sqlalchemy import and_

import app
from app import db
from app.models import Cases
from app.models import Client
from app.models.authorization import CaseAccessLevel
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

log = app.logger


def ac_get_mask_full_permissions():
    """
    Return access mask for full permissions
    """
    am = 0
    for perm in Permissions._member_names_:
        am |= Permissions[perm].value

    return am


def ac_get_mask_analyst():
    """
    Return a standard access mask for analysts
    """
    am = 0
    am |= Permissions.read_case_data.value
    am |= Permissions.write_case_data.value

    return am


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

            if perm & Permissions[std_perm].value:
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
        return None

    if ucea[0] & CaseAccessLevel.deny_all.value:
        return None

    for acl in access_level:
        if acl.value & ucea[0] == acl.value:
            return ucea[0]

    return None


def ac_user_has_case_access(user_id, cid, access_level):
    """
    Returns the user access level to a case
    """
    oca = OrganisationCaseAccess.query.filter(
        and_(OrganisationCaseAccess.case_id == cid,
             UserOrganisation.user_id == user_id,
             OrganisationCaseAccess.org_id == UserOrganisation.org_id)
    ).first()

    gca = GroupCaseAccess.query.filter(
        and_(GroupCaseAccess.case_id == cid,
             UserGroup.user_id == user_id,
             UserGroup.group_id == GroupCaseAccess.group_id)
    ).first()

    uca = UserCaseAccess.query.filter(
        and_(UserCaseAccess.case_id == cid,
             UserCaseAccess.user_id == user_id)
    ).first()

    fca = 0

    for ac_l in CaseAccessLevel:
        if uca:
            if uca.access_level & ac_l.value == ac_l.value:
                fca |= uca.access_level
            continue

        elif gca:
            if gca.access_level & ac_l.value == ac_l.value:
                fca |= gca.access_level
            continue

        elif oca:
            if oca.access_level & ac_l.value == ac_l.value:
                fca |= oca.access_level
                continue

    if not fca or fca & CaseAccessLevel.deny_all.value == CaseAccessLevel.deny_all.value:
        return False

    for acl in access_level:
        if acl.value & fca == acl.value:
            return True

    return False


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
    log.info(f'User {user_id} current access : {grouped_uca}')
    log.info(f'User {user_id} target access : {target_ucas}')

    ucea_to_add = {}
    cid_to_remove = []

    for case_id in target_ucas:
        if case_id not in grouped_uca:
            ucea_to_add.update({case_id: target_ucas[case_id]})
        else:
            if grouped_uca[case_id] & target_ucas[case_id] != target_ucas[case_id]:
                cid_to_remove.append(case_id)
                ucea_to_add.update({case_id: target_ucas[case_id]})

    for prev_case_id in grouped_uca:
        if prev_case_id not in target_ucas:
            cid_to_remove.append(prev_case_id)

    UserCaseEffectiveAccess.query.where(and_(
        UserCaseEffectiveAccess.user_id == user_id,
        UserCaseEffectiveAccess.case_id.in_(cid_to_remove)
    )).delete()

    log.info(f'User {user_id} access to add : {ucea_to_add}')
    log.info(f'User {user_id} access to remove : {cid_to_remove}')

    for case_id in ucea_to_add:
        ucea = UserCaseEffectiveAccess()
        ucea.user_id = user_id
        ucea.case_id = case_id
        ucea.access_level = ucea_to_add[case_id]
        db.session.add(ucea)

    db.session.commit()

    return


def ac_get_user_cases_access(user_id):
    ocas = OrganisationCaseAccess.query.with_entities(
        Cases.case_id,
        OrganisationCaseAccess.access_level
    ).filter(
        and_(UserOrganisation.user_id == user_id,
             OrganisationCaseAccess.org_id == UserOrganisation.org_id)
    ).join(
        OrganisationCaseAccess.case,
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

    ucas = UserCaseAccess.query.with_entities(
        Cases.case_id,
        UserCaseAccess.access_level
    ).filter(
        and_(UserCaseAccess.user_id == user_id)
    ).join(
        UserCaseAccess.case
    ).all()

    effective_cases_access = {}
    for oca in ocas:
        if oca.case_id in effective_cases_access:
            effective_cases_access[oca.case_id] = oca.access_level
        else:
            effective_cases_access[oca.case_id] = oca.access_level

        if effective_cases_access[oca.case_id] & CaseAccessLevel.deny_all.value == CaseAccessLevel.deny_all.value:
            effective_cases_access[oca.case_id] = CaseAccessLevel.deny_all.value

    for gca in gcas:
        if gca.case_id in effective_cases_access:
            effective_cases_access[gca.case_id] = gca.access_level
        else:
            effective_cases_access[gca.case_id] = gca.access_level

        if effective_cases_access[gca.case_id] & CaseAccessLevel.deny_all.value == CaseAccessLevel.deny_all.value:
            effective_cases_access[gca.case_id] = CaseAccessLevel.deny_all.value

    for uca in ucas:
        if uca.case_id in effective_cases_access:
            effective_cases_access[uca.case_id] |= uca.access_level
        else:
            effective_cases_access[uca.case_id] = uca.access_level

        if effective_cases_access[uca.case_id] & CaseAccessLevel.deny_all.value == CaseAccessLevel.deny_all.value:
            effective_cases_access[uca.case_id] = CaseAccessLevel.deny_all.value

    return effective_cases_access


def ac_trace_user_effective_cases_access(user_id):

    cases = Cases.query.with_entities(
        Cases.case_id,
        Cases.name
    ).order_by(
        Cases.case_id
    ).all()

    faccesses = {}

    for case in cases:
        faccesses[case.case_id] = {
            'case_info': {
                'case_name': case.name,
                'case_id': case.case_id
            },
            'user_access': [],
            'user_effective_access': []
        }

        accesses = faccesses[case.case_id]['user_access']
        effective = faccesses[case.case_id]['user_effective_access']

        oca = OrganisationCaseAccess.query.with_entities(
            Organisation.org_name,
            Organisation.org_id,
            Organisation.org_uuid,
            OrganisationCaseAccess.access_level
        ).filter(
            and_(OrganisationCaseAccess.case_id == case.case_id,
                 UserOrganisation.user_id == user_id,
                 OrganisationCaseAccess.org_id == UserOrganisation.org_id)
        ).first()

        gca = GroupCaseAccess.query.with_entities(
            Group.group_name,
            Group.group_id,
            Group.group_uuid,
            GroupCaseAccess.access_level
        ).filter(
            and_(GroupCaseAccess.case_id == case.case_id,
                 UserGroup.user_id == user_id,
                 UserGroup.group_id == GroupCaseAccess.group_id)
        ).join(
            GroupCaseAccess.group
        ).first()

        uca = UserCaseAccess.query.filter(
            and_(UserCaseAccess.case_id == case.case_id,
                 UserCaseAccess.user_id == user_id)
        ).first()

        fca = 0
        has_uca_deny_all = False
        has_gca_deny_all = False
        has_gca_overwritten = False
        has_uca_overwritten = False

        for ac_l in CaseAccessLevel:

            if uca:
                if uca.access_level & ac_l.value == ac_l.value:
                    fca |= uca.access_level
                    accesses.append({
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
                    effective.append(ac_l.name)
                    has_uca_overwritten = True
                    if ac_l.value == CaseAccessLevel.deny_all.value:
                        has_uca_deny_all = True

            if gca:
                if gca.access_level & ac_l.value == ac_l.value:
                    fca |= gca.access_level
                    if has_uca_overwritten or has_uca_deny_all:
                        state = 'Overwritten by user access'
                    else:
                        state = 'Effective'
                        effective.append(ac_l.name)

                    accesses.append({
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
                    has_gca_overwritten = True
                    if ac_l.value == CaseAccessLevel.deny_all.value:
                        has_gca_deny_all = True

            if oca:
                if oca.access_level & ac_l.value == ac_l.value:
                    fca |= oca.access_level

                    if has_uca_overwritten or has_uca_deny_all:
                        state = 'Overwritten by user access'
                    elif has_gca_overwritten or has_gca_deny_all:
                        state = 'Overwritten by group access'
                    else:
                        state = 'Effective'
                        effective.append(ac_l.name)

                    accesses.append({
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

    return faccesses


def ac_trace_case_access(case_id):

    case = Cases.query.with_entities(
        Cases.case_id,
        Cases.name
    ).filter(
        Cases.case_id == case_id
    ).first()

    if not case:
        return {}

    faccesses = {
        'case_info': {
            'case_name': case.name,
            'case_id': case.case_id
        },
        'users_access': []
    }

    accesses = faccesses['users_access']

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
                if uca.access_level & ac_l.value == ac_l.value:
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
                if gca.access_level & ac_l.value == ac_l.value:
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
                if oca.access_level & ac_l.value == ac_l.value:
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
        if access_level & CaseAccessLevel[ac].value:
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
    return ac_get_effective_permissions_of_user(user) & permission.value == permission


def ac_current_user_has_permission(permission):
    """
    Return True if current user has permission
    """
    return session['permissions'] & permission.value == permission