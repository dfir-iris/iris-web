#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

import secrets
import marshmallow
import traceback
from flask import Blueprint
from flask import request
from flask_login import current_user

from app import app
from app import db
from app.blueprints.rest.parsing import parse_comma_separated_identifiers
from app.datamgmt.manage.manage_users_db import add_case_access_to_user
from app.datamgmt.manage.manage_users_db import update_user_customers
from app.datamgmt.manage.manage_users_db import get_filtered_users
from app.datamgmt.manage.manage_users_db import create_user
from app.datamgmt.manage.manage_users_db import delete_user
from app.datamgmt.manage.manage_users_db import get_user
from app.datamgmt.manage.manage_users_db import get_user_by_username
from app.datamgmt.manage.manage_users_db import get_user_details
from app.datamgmt.manage.manage_users_db import get_users_list
from app.datamgmt.manage.manage_users_db import get_users_list_restricted
from app.datamgmt.manage.manage_users_db import remove_cases_access_from_user
from app.datamgmt.manage.manage_users_db import update_user
from app.datamgmt.manage.manage_users_db import update_user_groups
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.schema.marshables import UserSchema
from app.schema.marshables import BasicUserSchema
from app.schema.marshables import UserFullSchema

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success
from app.iris_engine.demo_builder import protect_demo_mode_user

manage_users_rest_blueprint = Blueprint('manage_users_rest', __name__)

log = app.logger


@manage_users_rest_blueprint.route('/manage/users/list', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def manage_users_list():

    users = get_users_list()

    return response_success('', data=users)


@manage_users_rest_blueprint.route('/manage/users/filter', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def manage_users_filter():

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    user_ids_str = request.args.get('user_ids', None, type=str)
    sort = request.args.get('sort', 'desc', type=str)

    if user_ids_str:
        try:
            user_ids_str = parse_comma_separated_identifiers(user_ids_str)
        except ValueError:
            return response_error('Invalid user_ids parameter')

    customer_id = request.args.get('customer_id', None, type=str)
    user_name = request.args.get('user_name', None, type=str)
    user_login = request.args.get('user_login', None, type=str)

    filtered_users = get_filtered_users(user_ids=user_ids_str,
                                        user_name=user_name,
                                        user_login=user_login,
                                        customer_id=customer_id,
                                        page=page,
                                        per_page=per_page,
                                        sort=sort)

    if filtered_users is None:
        return response_error('Filtering error')

    users = {
        'total': filtered_users.total,
        'users': BasicUserSchema().dump(filtered_users.items, many=True),
        'last_page': filtered_users.pages,
        'current_page': filtered_users.page,
        'next_page': filtered_users.next_num if filtered_users.has_next else None
    }

    return response_success(data=users)


@manage_users_rest_blueprint.route('/manage/users/add', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def add_user():
    try:

        # validate before saving
        user_schema = UserSchema()
        jsdata = request.get_json()
        jsdata['user_id'] = 0
        jsdata['active'] = jsdata.get('active', True)
        cuser = user_schema.load(jsdata, partial=True)
        user = create_user(user_name=cuser.name,
                           user_login=cuser.user,
                           user_email=cuser.email,
                           user_password=cuser.password,
                           user_active=jsdata.get('active'),
                           user_is_service_account=cuser.is_service_account)

        udata = user_schema.dump(user)
        udata['user_api_key'] = user.api_key
        del udata['user_password']

        if cuser:
            track_activity("created user {}".format(user.user),  ctx_less=True)
            return response_success("user created", data=udata)

        return response_error("Unable to create user for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@manage_users_rest_blueprint.route('/manage/users/<int:cur_id>', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def view_user(cur_id):

    user = get_user_details(user_id=cur_id)

    if not user:
        return response_error("Invalid user ID")

    return response_success(data=user)


@manage_users_rest_blueprint.route('/manage/users/<int:cur_id>/groups/update', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def manage_user_group_(cur_id):

    if not request.is_json:
        return response_error("Invalid request")

    if not request.json.get('groups_membership'):
        return response_error("Invalid request")

    if type(request.json.get('groups_membership')) is not list:
        return response_error("Expected list of groups ID")

    user = get_user_details(cur_id)
    if not user:
        return response_error("Invalid user ID")

    update_user_groups(user_id=cur_id,
                       groups=request.json.get('groups_membership'))

    track_activity(f"groups membership of user {cur_id} updated", ctx_less=True)

    return response_success("User groups updated", data=user)


@manage_users_rest_blueprint.route('/manage/users/<int:cur_id>/customers/update', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def manage_user_customers_(cur_id):

    if not request.is_json:
        return response_error("Invalid request")

    if not request.json.get('customers_membership'):
        return response_error("Invalid request")

    if type(request.json.get('customers_membership')) is not list:
        return response_error("Expected list of customers ID")

    user = get_user_details(cur_id)
    if not user:
        return response_error('Invalid user ID')

    update_user_customers(user_id=cur_id, customers=request.json.get('customers_membership'))

    track_activity(f"customers membership of user {cur_id} updated", ctx_less=True)

    return response_success("User customers updated", data=user)


@manage_users_rest_blueprint.route('/manage/users/<int:cur_id>/cases-access/update', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def manage_user_cac_add_case(cur_id):

    if not request.is_json:
        return response_error("Invalid request, expecting JSON")

    data = request.get_json()
    if not data:
        return response_error("Invalid request, expecting JSON")

    user = get_user(cur_id)
    if not user:
        return response_error("Invalid user ID")

    if not isinstance(data.get('access_level'), int):
        try:
            data['access_level'] = int(data.get('access_level'))
        except:
            return response_error("Expecting access_level as int")

    if not isinstance(data.get('cases_list'), list):
        return response_error("Expecting cases_list as list")

    user, logs = add_case_access_to_user(user, data.get('cases_list'), data.get('access_level'))
    if not user:
        return response_error(msg=logs)

    track_activity(f"case access level {data.get('access_level')} for case(s) {data.get('cases_list')} "
                   f"set for user {user.user}", ctx_less=True)

    group = get_user_details(cur_id)

    return response_success(data=group)


@manage_users_rest_blueprint.route('/manage/users/<int:cur_id>/cases-access/delete', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def manage_user_cac_delete_cases(cur_id):

    user = get_user(cur_id)
    if not user:
        return response_error("Invalid user ID")

    if not request.is_json:
        return response_error("Invalid request")

    data = request.get_json()
    if not data:
        return response_error("Invalid request")

    if not isinstance(data.get('cases'), list):
        return response_error("Expecting cases as list")

    try:

        success, logs = remove_cases_access_from_user(user.id, data.get('cases'))
        db.session.commit()

    except Exception as e:
        log.error("Error while removing cases access from user: {}".format(e))
        log.error(traceback.format_exc())
        return response_error(msg=str(e))

    if success:
        track_activity(f"cases access for case(s) {data.get('cases')} deleted for user {user.user}",
                       ctx_less=True)

        user = get_user_details(cur_id)

        return response_success(msg="User case access updated", data=user)

    return response_error(msg=logs)


@manage_users_rest_blueprint.route('/manage/users/update/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def update_user_api(cur_id):

    try:
        user = get_user(cur_id)
        if not user:
            return response_error("Invalid user ID for this case")

        if protect_demo_mode_user(user):
            return ac_api_return_access_denied()

        # validate before saving
        user_schema = UserSchema()
        jsdata = request.get_json()
        jsdata['user_id'] = cur_id
        cuser = user_schema.load(jsdata, instance=user, partial=True)
        update_user(password=jsdata.get('user_password'),
                    user=user)
        db.session.commit()

        if cuser:
            track_activity("updated user {}".format(user.user), ctx_less=True)
            return response_success("User updated", data=user_schema.dump(user))

        return response_error("Unable to update user for internal reasons")

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@manage_users_rest_blueprint.route('/manage/users/deactivate/<int:cur_id>', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def deactivate_user_api(cur_id):

    user = get_user(cur_id)
    if not user:
        return response_error("Invalid user ID for this case")

    if protect_demo_mode_user(user):
        return ac_api_return_access_denied()

    if current_user.id == cur_id:
        return response_error('We do not recommend deactivating yourself for obvious reasons')

    user.active = False
    db.session.commit()
    user_schema = UserSchema()

    track_activity(f"user {user.user} deactivated", ctx_less=True)
    return response_success("User deactivated", data=user_schema.dump(user))


@manage_users_rest_blueprint.route('/manage/users/activate/<int:cur_id>', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def activate_user_api(cur_id):

    user = get_user(cur_id)
    if not user:
        return response_error("Invalid user ID for this case")

    if protect_demo_mode_user(user):
        return ac_api_return_access_denied()

    user.active = True
    db.session.commit()
    user_schema = UserSchema()

    track_activity(f"user {user.user} activated", ctx_less=True)
    return response_success("User activated", data=user_schema.dump(user))


@manage_users_rest_blueprint.route('/manage/users/renew-api-key/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def renew_user_api_key(cur_id):

    user = get_user(cur_id)
    if not user:
        return response_error("Invalid user ID for this case")

    if protect_demo_mode_user(user):
        return ac_api_return_access_denied()

    user.api_key = secrets.token_urlsafe(nbytes=64)
    db.session.commit()

    user_schema = UserFullSchema()

    track_activity(f"API key of user {user.user} renewed", ctx_less=True)
    return response_success(f"API key of user {user.user} renewed", data=user_schema.dump(user))


@manage_users_rest_blueprint.route('/manage/users/delete/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def view_delete_user(cur_id):

    try:

        user = get_user(cur_id)
        if not user:
            return response_error("Invalid user ID")

        if protect_demo_mode_user(user):
            return ac_api_return_access_denied()

        if user.active is True:
            track_activity(message="tried to delete active user ID {}".format(cur_id), ctx_less=True)
            return response_error("Cannot delete active user")

        delete_user(user.id)

        track_activity(message="deleted user ID {}".format(cur_id), ctx_less=True)
        return response_success("Deleted user ID {}".format(cur_id))

    except Exception as e:
        print(e)
        db.session.rollback()
        track_activity(message="tried to delete active user ID {}".format(cur_id), ctx_less=True)
        return response_error("Cannot delete active user")


# Unrestricted section - non admin available
@manage_users_rest_blueprint.route('/manage/users/lookup/id/<int:cur_id>', methods=['GET'])
@ac_api_requires()
def exists_user_restricted(cur_id):

    user = get_user(cur_id)
    if not user:
        return response_error("Invalid user ID")

    output = {
        "user_login": user.user,
        "user_id": user.id,
        "user_name": user.name
    }

    return response_success(data=output)


@manage_users_rest_blueprint.route('/manage/users/lookup/login/<string:login>', methods=['GET'])
@ac_api_requires()
def lookup_name_restricted(login):
    user = get_user_by_username(login)
    if not user:
        return response_error("Invalid login")

    output = {
        "user_login": user.user,
        "user_id": user.id,
        "user_uuid": user.uuid,
        "user_name": user.name,
        "user_email": user.email,
        "user_active": user.active
    }

    return response_success(data=output)


@manage_users_rest_blueprint.route('/manage/users/restricted/list', methods=['GET'])
@ac_api_requires()
def manage_users_list_restricted():

    users = get_users_list_restricted()

    return response_success('', data=users)
