#  IRIS Source Code
#  DFIR IRIS
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
import random
import string

from flask_login import current_user

from app import app
from app import bc
from app import db
from app.datamgmt.manage.manage_groups_db import add_case_access_to_group
from app.datamgmt.manage.manage_users_db import add_user_to_group
from app.datamgmt.manage.manage_users_db import add_user_to_organisation
from app.datamgmt.manage.manage_users_db import user_exists
from app.iris_engine.access_control.utils import ac_add_users_multi_effective_access
from app.models import Cases
from app.models import Client
from app.models import get_or_create
from app.models.authorization import CaseAccessLevel
from app.models.authorization import User

log = app.logger


def protect_demo_mode_user(user):
    if app.config.get('DEMO_MODE_ENABLED') != 'True':
        return False

    users_p = [f'user_std_{i}' for i in range(1, int(app.config.get('DEMO_USERS_COUNT', 10)))]
    users_p += [f'adm_{i}' for i in range(1, int(app.config.get('DEMO_ADM_COUNT', 4)))]

    if current_user.id != 1 and user.id == 1:
        return True

    if user.user in users_p:
        return True

    return False


def protect_demo_mode_group(group):
    if app.config.get('DEMO_MODE_ENABLED') != 'True':
        return False

    if current_user.id != 1 and group.group_id in [1, 2]:
        return True

    return False


def gen_demo_admins(count, seed_adm):
    random.seed(seed_adm, version=2)
    for i in range(1, count):
        yield f'Adm {i}',\
              f'adm_{i}', \
              ''.join(random.choices(string.printable[:-6], k=16)), \
              ''.join(random.choices(string.ascii_letters, k=64))


def gen_demo_users(count, seed_user):
    random.seed(seed_user, version=2)
    for i in range(1, count):
        yield f'User Std {i}',\
              f'user_std_{i}', \
              ''.join(random.choices(string.printable[:-6], k=16)), \
              ''.join(random.choices(string.ascii_letters, k=64))


def create_demo_users(def_org, gadm, ganalystes, users_count, seed_user, adm_count, seed_adm):
    users = {
        'admins': [],
        'users': [],
        'gadm': gadm,
        'ganalystes': ganalystes
    }

    for name, username, pwd, api_key in gen_demo_users(users_count, seed_user):

        # Create default users
        user = user_exists(username, f'{username}@iris.local')
        if not user:
            password = bc.generate_password_hash(pwd.encode('utf-8')).decode('utf-8')
            user = User(
                user=username,
                password=password,
                email=f'{username}@iris.local',
                name=name,
                active=True)

            user.api_key = api_key
            db.session.add(user)
            db.session.commit()
            add_user_to_group(user_id=user.id, group_id=ganalystes.group_id)
            add_user_to_organisation(user_id=user.id, org_id=def_org.org_id)
            db.session.commit()
            log.info(f'Created demo user: {user.user} -  {pwd}')

        users['users'].append(user)

    for name, username, pwd, api_key in gen_demo_admins(adm_count, seed_adm):
        user = user_exists(username, f'{username}@iris.local')
        if not user:
            password = bc.generate_password_hash(pwd.encode('utf-8')).decode('utf-8')
            user = User(
                user=username,
                password=password,
                email=f'{username}@iris.local',
                name=name,
                active=True)

            user.api_key = api_key
            db.session.add(user)
            db.session.commit()
            add_user_to_group(user_id=user.id, group_id=gadm.group_id)
            add_user_to_organisation(user_id=user.id, org_id=def_org.org_id)
            db.session.commit()
            log.info(f'Created demo admin: {user.user} - {pwd}')

        users['admins'].append(user)

    return users


def create_demo_cases(users_data: dict = None, cases_count: int = 0, clients_count: int = 0):

    clients = []
    for client_index in range(0, clients_count):
        client = get_or_create(db.session,
                      Client,
                      name=f'Client {client_index}',
                      description=f'Description for client {client_index}')
        clients.append(client.client_id)

    cases_list = []
    for case_index in range(0, cases_count):
        if demo_case_exists(f"Unrestricted Case {case_index}", f"SOC-{case_index}") is not None:
            log.info(f'Restricted case {case_index} already exists')
            continue

        case = Cases(
            name=f"Unrestricted Case {case_index}",
            description="This is a demonstration of an unrestricted case",
            soc_id=f"SOC-{case_index}",
            user=random.choice(users_data['users']),
            client_id=random.choice(clients)
        )

        case.validate_on_build()
        case.save()

        db.session.commit()
        cases_list.append(case.case_id)
        log.info('Added unrestricted case {}'.format(case.name))

    log.info('Setting permissions for unrestricted cases')
    add_case_access_to_group(group=users_data['ganalystes'],
                             cases_list=cases_list,
                             access_level=CaseAccessLevel.full_access.value)

    add_case_access_to_group(group=users_data['gadm'],
                             cases_list=cases_list,
                             access_level=CaseAccessLevel.full_access.value)

    ac_add_users_multi_effective_access(users_list=[u.id for u in users_data['users']],
                                        cases_list=cases_list,
                                        access_level=CaseAccessLevel.full_access.value)

    ac_add_users_multi_effective_access(users_list=[u.id for u in users_data['admins']],
                                        cases_list=cases_list,
                                        access_level=CaseAccessLevel.full_access.value)

    cases_list = []
    for case_index in range(0, int(cases_count/2)):
        if demo_case_exists(f"Restricted Case {case_index}", f"SOC-RSTRCT-{case_index}") is not None:
            log.info(f'Restricted case {case_index} already exists')
            continue

        case = Cases(
            name=f"Restricted Case {case_index}",
            description="This is a demonstration of a restricted case that shouldn't be visible to analyst",
            soc_id=f"SOC-RSTRCT-{case_index}",
            user=random.choice(users_data['admins']),
            client_id=random.choice(clients)
        )
        case.validate_on_build()
        case.save()

        db.session.commit()
        cases_list.append(case.case_id)
        log.info('Added restricted case {}'.format(case.name))

    add_case_access_to_group(group=users_data['ganalystes'],
                             cases_list=cases_list,
                             access_level=CaseAccessLevel.deny_all.value)

    ac_add_users_multi_effective_access(users_list=[u.id for u in users_data['users']],
                                        cases_list=cases_list,
                                        access_level=CaseAccessLevel.deny_all.value)


    add_case_access_to_group(group=users_data['gadm'],
                             cases_list=cases_list,
                             access_level=CaseAccessLevel.full_access.value)

    ac_add_users_multi_effective_access(users_list=[u.id for u in users_data['admins']],
                                        cases_list=cases_list,
                                        access_level=CaseAccessLevel.full_access.value)

    log.info('Demo data created successfully')


def demo_case_exists(name, soc_id):
    return db.session.query(Cases).filter(Cases.name.like(f'%{name}'),
                                          Cases.soc_id == soc_id).first()
