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

import datetime
import traceback
from flask import Blueprint
from flask import request
from flask_login import current_user
from marshmallow import ValidationError

from app import ac_current_user_has_permission
from app.blueprints.access_controls import ac_api_requires
from app.datamgmt.client.client_db import create_client
from app.datamgmt.client.client_db import create_contact
from app.datamgmt.client.client_db import delete_client
from app.datamgmt.client.client_db import delete_contact
from app.datamgmt.client.client_db import get_client
from app.datamgmt.client.client_db import get_client_api
from app.datamgmt.client.client_db import get_client_cases
from app.datamgmt.client.client_db import get_client_contacts
from app.datamgmt.client.client_db import get_client_list
from app.datamgmt.client.client_db import update_client
from app.datamgmt.client.client_db import update_contact
from app.datamgmt.exceptions.ElementExceptions import ElementInUseException
from app.datamgmt.exceptions.ElementExceptions import ElementNotFoundException
from app.datamgmt.manage.manage_users_db import add_user_to_customer
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.schema.marshables import ContactSchema
from app.schema.marshables import CustomerSchema
from app.blueprints.access_controls import ac_api_requires_client_access
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success

manage_customers_rest_blueprint = Blueprint('manage_customers_rest', __name__)


@manage_customers_rest_blueprint.route('/manage/customers/list', methods=['GET'])
@ac_api_requires(Permissions.customers_read)
def list_customers():
    user_is_server_administrator = ac_current_user_has_permission(Permissions.server_administrator)
    client_list = get_client_list(current_user_id=current_user.id,
                                  is_server_administrator=user_is_server_administrator)

    return response_success("", data=client_list)


@manage_customers_rest_blueprint.route('/manage/customers/<int:client_id>', methods=['GET'])
@ac_api_requires(Permissions.customers_read)
@ac_api_requires_client_access()
def view_customer(client_id):

    customer = get_client_api(client_id)

    customer['contacts'] = ContactSchema().dump(get_client_contacts(client_id), many=True)

    return response_success(data=customer)


@manage_customers_rest_blueprint.route('/manage/customers/<int:client_id>/contacts/<int:contact_id>/update', methods=['POST'])
@ac_api_requires(Permissions.customers_write)
@ac_api_requires_client_access()
def customer_update_contact(client_id, contact_id):

    if not request.is_json:
        return response_error("Invalid request")

    if not get_client(client_id):
        return response_error(f"Invalid Customer ID {client_id}")

    try:

        contact = update_contact(request.json, contact_id, client_id)

    except ValidationError as e:
        return response_error(msg='Error update contact', data=e.messages)

    except Exception as e:
        print(traceback.format_exc())
        return response_error(f'An error occurred during contact update. {e}')

    track_activity(f"Updated contact {contact.contact_name}", ctx_less=True)

    # Return the customer
    contact_schema = ContactSchema()
    return response_success("Added successfully", data=contact_schema.dump(contact))


@manage_customers_rest_blueprint.route('/manage/customers/<int:client_id>/contacts/add', methods=['POST'])
@ac_api_requires(Permissions.customers_write)
@ac_api_requires_client_access()
def customer_add_contact(client_id):

    if not request.is_json:
        return response_error("Invalid request")

    if not get_client(client_id):
        return response_error(f"Invalid Customer ID {client_id}")

    try:

        contact = create_contact(request.json, client_id)

    except ValidationError as e:
        return response_error(msg='Error adding contact', data=e.messages)

    except Exception as e:
        print(traceback.format_exc())
        return response_error(f'An error occurred during contact addition. {e}')

    track_activity(f"Added contact {contact.contact_name}", ctx_less=True)

    # Return the customer
    contact_schema = ContactSchema()
    return response_success("Added successfully", data=contact_schema.dump(contact))


@manage_customers_rest_blueprint.route('/manage/customers/<int:client_id>/cases', methods=['GET'])
@ac_api_requires(Permissions.customers_read)
@ac_api_requires_client_access()
def get_customer_case_stats(client_id):

    cases = get_client_cases(client_id)
    cases_list = []

    now = datetime.date.today()
    cases_stats = {
        'cases_last_month': 0,
        'cases_last_year': 0,
        'open_cases': 0,
        'last_year': now.year - 1,
        'last_month': now.month - 1,
        'cases_rolling_week': 0,
        'cases_current_month': 0,
        'cases_current_year': 0,
        'ratio_year': 0,
        'ratio_month': 0,
        'average_case_duration': 0,
        'cases_total': len(cases)
    }

    last_month_start = datetime.date.today() - datetime.timedelta(days=30)
    last_month_end = datetime.date(now.year, now.month, 1)

    last_year_start = datetime.date(now.year - 1, 1, 1)
    last_year_end = datetime.date(now.year - 1, 12, 31)
    this_year_start = datetime.date(now.year, 1, 1)
    this_month_start = datetime.date(now.year, now.month, 1)

    for case in cases:
        cases_list.append(case._asdict())
        if now - datetime.timedelta(days=7) <= case.open_date <= now:
            cases_stats['cases_rolling_week'] += 1

        if this_month_start <= case.open_date <= now:
            cases_stats['cases_current_month'] += 1

        if this_year_start <= case.open_date <= now:
            cases_stats['cases_current_year'] += 1

        if last_month_start < case.open_date < last_month_end:
            cases_stats['cases_last_month'] += 1

        if last_year_start <= case.open_date <= last_year_end:
            cases_stats['cases_last_year'] += 1

        if case.close_date is None:
            cases_stats['open_cases'] += 1

        if cases_stats['cases_last_year'] == 0:
            st = 1
            et = cases_stats['cases_current_year'] + 1
        else:
            st = cases_stats['cases_last_year']
            et = cases_stats['cases_current_year']

        cases_stats['ratio_year'] = ((et - st)/(st)) * 100

        if cases_stats['cases_last_month'] == 0:
            st = 1
            et = cases_stats['cases_current_month'] + 1
        else:
            st = cases_stats['cases_last_month']
            et = cases_stats['cases_current_month']

        cases_stats['ratio_month'] = ((et - st)/(st)) * 100

        if (case.close_date is not None) and (case.open_date is not None):
            cases_stats['average_case_duration'] += (case.close_date - case.open_date).days

    if cases_stats['cases_total'] > 0 and cases_stats['open_cases'] > 0 and cases_stats['average_case_duration'] > 0:
        cases_stats['average_case_duration'] = cases_stats['average_case_duration'] / (cases_stats['cases_total'] - cases_stats['open_cases'])

    cases = {
        'cases': cases_list,
        'stats': cases_stats
    }

    return response_success(data=cases)


@manage_customers_rest_blueprint.route('/manage/customers/update/<int:client_id>', methods=['POST'])
@ac_api_requires(Permissions.customers_write)
@ac_api_requires_client_access()
def view_customers(client_id):
    if not request.is_json:
        return response_error("Invalid request")

    try:
        client = update_client(client_id, request.json)

    except ElementNotFoundException:
        return response_error('Invalid Customer ID')

    except ValidationError as e:
        return response_error("", data=e.messages)

    except Exception as e:
        print(traceback.format_exc())
        return response_error(f'An error occurred during Customer update. {e}')

    client_schema = CustomerSchema()
    return response_success("Customer updated", client_schema.dump(client))


@manage_customers_rest_blueprint.route('/manage/customers/add', methods=['POST'])
@ac_api_requires(Permissions.customers_write)
def add_customers():
    if not request.is_json:
        return response_error("Invalid request")

    try:
        client = create_client(request.json)
    except ValidationError as e:
        return response_error(msg='Error adding customer', data=e.messages)
    except Exception as e:
        print(traceback.format_exc())
        return response_error(f'An error occurred during customer addition. {e}')

    track_activity(f"Added customer {client.name}", ctx_less=True)

    # Associate the created customer with the current user
    add_user_to_customer(current_user.id, client.client_id)

    # Return the customer
    client_schema = CustomerSchema()
    return response_success("Added successfully", data=client_schema.dump(client))


@manage_customers_rest_blueprint.route('/manage/customers/delete/<int:client_id>', methods=['POST'])
@ac_api_requires(Permissions.customers_write)
@ac_api_requires_client_access()
def delete_customers(client_id):
    try:

        delete_client(client_id)

    except ElementNotFoundException:
        return response_error('Invalid Customer ID')

    except ElementInUseException:
        return response_error('Cannot delete a referenced customer')

    except Exception:
        return response_error('An error occurred during customer deletion')

    track_activity(f"Deleted Customer with ID {client_id}", ctx_less=True)

    return response_success("Deleted successfully")


@manage_customers_rest_blueprint.route('/manage/customers/<int:client_id>/contacts/<int:contact_id>/delete', methods=['POST'])
@ac_api_requires(Permissions.customers_write)
@ac_api_requires_client_access()
def delete_contact_route(client_id, contact_id):
    try:

        delete_contact(contact_id)

    except ElementNotFoundException:
        return response_error('Invalid contact ID')

    except ElementInUseException:
        return response_error('Cannot delete a referenced contact')

    except Exception:
        return response_error('An error occurred during contact deletion')

    track_activity(f"Deleted Customer with ID {contact_id}", ctx_less=True)

    return response_success("Deleted successfully")
