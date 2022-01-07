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

from app import bc, db
from app.models import User, UserRoles, Role


def get_user(user_id):
    user = User.query.filter(User.id == user_id).first()
    return user


def get_user_details(user_id):

    user = User.query.filter(User.id == user_id).first()

    if not user:
        return None

    row = {}
    row['user_id'] = user.id
    row['user_name'] = user.name
    row['user_login'] = user.user
    roles = []
    for role in user.roles:
        roles.append({
            'role_name': role.name,
            'role_id': role.id
        })

    row['user_roles'] = roles
    row['user_active'] = user.active

    return row


def get_user_by_username(username):
    user = User.query.filter(User.user == username).first()
    return user


def get_users_list():
    users = User.query.all()

    output = []
    for user in users:
        row = {}
        row['user_id'] = user.id
        row['user_name'] = user.name
        row['user_login'] = user.user
        roles = []
        for role in user.roles:
            roles.append(role.name)

        row['user_roles'] = roles
        row['user_active'] = user.active
        output.append(row)

    return output


def create_user(user_name, user_login, user_password, user_email, user_isadmin):
    pw_hash = bc.generate_password_hash(user_password.encode('utf8')).decode('utf8')

    user = User(user_login, user_name, user_email, pw_hash, True)
    user.save()

    if user_isadmin:
        ur = UserRoles()
        ur.user_id = user.id
        ur.role_id = Role.query.with_entities(Role.id).filter(Role.name == 'administrator').first()
        db.session.add(ur)

    db.session.commit()
    return user


def update_user(password, user_isadmin, user):

    if password:
        pw_hash = bc.generate_password_hash(password.encode('utf8')).decode('utf8')
        user.password = pw_hash

    if user_isadmin != None:
        if user_isadmin:
            ur = UserRoles()
            ur.user_id = user.id
            ur.role_id = Role.query.with_entities(Role.id).filter(Role.name == 'administrator').first()
            db.session.add(ur)

        else:
            role_id = Role.query.with_entities(Role.id).filter(Role.name == 'administrator').first()
            UserRoles.query.filter(UserRoles.user_id == user.id, UserRoles.role_id == role_id).delete()

    db.session.commit()

    return user


def delete_user(user_id):
    User.query.filter(User.id == user_id).delete()
    db.session.commit()


def user_exists(user_name, user_email):
    user = User.query.filter_by(user=user_name).first()
    user_by_email = User.query.filter_by(email=user_email).first()

    return user or user_by_email

