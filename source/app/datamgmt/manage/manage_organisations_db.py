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
from app.datamgmt.case.case_db import get_case
from app.datamgmt.manage.manage_users_db import get_user_primary_org
from app.iris_engine.access_control.utils import ac_access_level_mask_from_val_list
from app.iris_engine.access_control.utils import ac_access_level_to_list
from app.iris_engine.access_control.utils import ac_auto_update_user_effective_access
from app.iris_engine.access_control.utils import ac_permission_to_list
from app.models import Cases
from app.models.authorization import Group
from app.models.authorization import GroupCaseAccess
from app.models.authorization import Organisation
from app.models.authorization import OrganisationCaseAccess
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
        UserOrganisation.user, UserOrganisation.org
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


def get_orgs_details(org_id):
    org = get_org_with_members(org_id)

    if not org:
        return org

    organisation_accesses = OrganisationCaseAccess.query.with_entities(
        OrganisationCaseAccess.access_level,
        OrganisationCaseAccess.case_id,
        Cases.name.label('case_name')
    ).join(
        OrganisationCaseAccess.case
    ).filter(
        OrganisationCaseAccess.org_id == org_id
    ).all()

    orgs_case_access = []
    for korg in organisation_accesses:
        orgs_case_access.append({
            "access_level": korg.access_level,
            "access_level_list": ac_access_level_to_list(korg.access_level),
            "case_id": korg.case_id,
            "case_name": korg.case_name
        })

    setattr(org, 'org_cases_access', orgs_case_access)

    return org


def update_org_members(org, members):
    if not org:
        return None

    cur_org_members = UserOrganisation.query.with_entities(
        UserOrganisation.user_id
    ).filter(UserOrganisation.org_id == org.org_id).all()

    cur_org_members = set([member.user_id for member in cur_org_members])
    set_members = set([int(mber) for mber in members])

    users_to_add = set_members - cur_org_members
    users_to_remove = cur_org_members - set_members

    for uid in users_to_add:
        user = User.query.filter(User.id == uid).first()
        if user:
            prim_org = get_user_primary_org(user.id)

            uo = UserOrganisation()
            uo.org_id = org.org_id
            uo.user_id = user.id
            uo.is_primary_org = prim_org is None
            db.session.add(uo)

            ac_auto_update_user_effective_access(uid)

    for uid in users_to_remove:
        UserOrganisation.query.filter(
            and_(UserOrganisation.user_id == uid,
                 UserOrganisation.org_id == org.org_id,
                 UserOrganisation.is_primary_org == False)
        ).delete()

        ac_auto_update_user_effective_access(uid)

    db.session.commit()

    return org


def remove_user_from_organisation(org, member):
    if not org:
        return False, 'Invalid organisation'

    org = UserOrganisation.query.filter(
        and_(UserOrganisation.org_id == org.org_id,
             UserOrganisation.user_id == member.id)
    ).first()

    if org and org.is_primary_org:
        return False, f'Cannot delete user from primary organisation {org.org_id}. Change it before deleting.'

    db.session.commit()

    ac_auto_update_user_effective_access(member.id)

    return True, f'User removed from organisation {org.org_id}'


def delete_organisation(org):
    if not org:
        return None

    UserOrganisation.query.filter(UserOrganisation.org_id == org.org_id).delete()
    OrganisationCaseAccess.query.filter(OrganisationCaseAccess.org_id == org.org_id).delete()

    db.session.delete(org)
    db.session.commit()


def get_user_organisations(user_id):
    orgs = Organisation.query.join(
        UserOrganisation,
        Organisation.org_id == UserOrganisation.org_id
    ).filter(
        UserOrganisation.user_id == user_id
    ).all()

    return orgs


def is_user_in_org(user_id, org_id):
    return UserOrganisation.query.filter(
        and_(UserOrganisation.user_id == user_id,
             UserOrganisation.org_id == org_id)
    ).first() is not None


def add_case_access_to_org(org, cases_list, access_level):
    if not org:
        return None, "Invalid organisation"

    for case_id in cases_list:
        case = get_case(case_id)
        if not case:
            return None, "Invalid case ID"

        access_level_mask = ac_access_level_mask_from_val_list([access_level])

        ocas = OrganisationCaseAccess.query.filter(
            and_(
                OrganisationCaseAccess.case_id == case_id,
                OrganisationCaseAccess.org_id == org.org_id
            )).all()
        if ocas:
            for oca in ocas:
                db.session.delete(oca)

        oca = OrganisationCaseAccess()
        oca.org_id = org.org_id
        oca.access_level = access_level_mask
        oca.case_id = case_id
        db.session.add(oca)

    db.session.commit()
    return org, "Updated"


def remove_case_access_from_organisation(org_id, case_id):
    if not org_id or type(org_id) is not int:
        return

    if not case_id or type(case_id) is not int:
        return

    OrganisationCaseAccess.query.filter(
        and_(
            OrganisationCaseAccess.case_id == case_id,
            OrganisationCaseAccess.org_id == org_id
        )).delete()

    db.session.commit()
    return
