#!/usr/bin/env python3
#
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
import string

import random

from app import app
from app import bc
from app import db
from app.datamgmt.manage.manage_users_db import add_user_to_group
from app.datamgmt.manage.manage_users_db import add_user_to_organisation
from app.datamgmt.manage.manage_users_db import user_exists
from app.models.authorization import User


log = app.logger


def gen_demo_admins(count, seed_adm):
    random.seed(seed_adm, version=2)
    for i in range(1, count):
        yield f'Adm {i}',\
              f'adm_{i}', \
              f"{''.join(random.choices(string.printable[:-6], k=16))}_{i}", \
              f"{''.join(random.choices(string.ascii_letters, k=62))}_{i}"


def gen_demo_users(count, seed_user):
    random.seed(seed_user, version=2)
    for i in range(1, count):
        yield f'User Std {i}',\
              f'user_std_{i}', \
              f"{''.join(random.choices(string.printable[:-6], k=16))}_{i}", \
              f"{''.join(random.choices(string.ascii_letters, k=62))}_{i}"


def create_demo_users(def_org, gadm, ganalystes, users_count, seed_user, adm_count, seed_adm):

    for name, username, pwd, api_key in gen_demo_users(users_count, seed_user):

        # Create default users
        if not user_exists(username, f'{username}@iris.local'):
            pwd = bc.generate_password_hash(pwd.encode('utf-8')).decode('utf-8')
            user = User(
                user=username,
                password=pwd,
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

    for name, username, pwd, api_key in gen_demo_admins(adm_count, seed_adm):
        if not user_exists(username, f'{username}@iris.local'):
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
