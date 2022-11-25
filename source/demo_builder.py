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
from app import db
from app.datamgmt.manage.manage_users_db import add_user_to_group
from app.datamgmt.manage.manage_users_db import add_user_to_organisation
from app.models.authorization import User


log = app.logger


def create_demo_users(def_org, gadm, ganalystes, seed_user, seed_adm):

    random.seed(seed_user, version=2)
    user_pwd = ''.join(random.choices(string.printable, k=16))
    api_key = ''.join(random.choices(string.printable, k=62))

    random.seed(seed_adm, version=2)
    adm_pwd = ''.join(random.choices(string.printable, k=16))
    api_key_adm = ''.join(random.choices(string.printable, k=62))

    for i in range(0, 10):
        # Create default admin user
        user = User(
            user=f'user_std_{i}',
            password=f'{user_pwd}_{i}',
            email=f'user_std_{i}@iris.local',
            name=f'User Std {i}',
            active=True)
        user.api_key = api_key + f'_{i}'
        db.session.add(user)
        db.session.commit()
        add_user_to_group(user_id=user.id, group_id=ganalystes.group_id)
        add_user_to_organisation(user_id=user.id, org_id=def_org.org_id)
        db.session.commit()
        log.info(f'Created demo user: {user.user}')

    for i in range(0, 4):
        # Create default admin user
        user = User(
            user=f'user_adm_{i}',
            password=f'{adm_pwd}_{i}',
            email=f'user_adm_{i}',
            name=f'Adm {i}',
            active=True)
        user.api_key = api_key_adm + f'_{i}'
        db.session.add(user)
        db.session.commit()
        add_user_to_group(user_id=user.id, group_id=gadm.group_id)
        add_user_to_organisation(user_id=user.id, org_id=def_org.org_id)
        log.info(f'Created demo admin: {user.user}')

        db.session.commit()

