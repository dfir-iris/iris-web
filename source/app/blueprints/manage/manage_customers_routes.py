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

# IMPORTS ------------------------------------------------
import traceback
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from marshmallow import ValidationError

from app.datamgmt.client.client_db import create_client
from app.datamgmt.client.client_db import delete_client
from app.datamgmt.client.client_db import get_client
from app.datamgmt.client.client_db import get_client_api
from app.datamgmt.client.client_db import get_client_list
from app.datamgmt.client.client_db import update_client
from app.datamgmt.exceptions.ElementExceptions import ElementInUseException
from app.datamgmt.exceptions.ElementExceptions import ElementNotFoundException
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.forms import AddCustomerForm
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.schema.marshables import CustomerSchema
from app.util import ac_api_requires
from app.util import ac_requires
from app.util import response_error
from app.util import response_success

manage_customers_blueprint = Blueprint(
    'manage_customers',
    __name__,
    template_folder='templates'
)


# CONTENT ------------------------------------------------
@manage_customers_blueprint.route('/manage/customers')
@ac_requires(Permissions.server_administrator)
def manage_customers(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_customers.manage_customers', cid=caseid))

    form = AddCustomerForm()

    # Return default page of case management
    return render_template('manage_customers.html', form=form)


@manage_customers_blueprint.route('/manage/customers/list')
@ac_api_requires(Permissions.server_administrator)
def list_customers(caseid):
    client_list = get_client_list()

    return response_success("", data=client_list)


@manage_customers_blueprint.route('/manage/customers/<int:cur_id>', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def view_customer(cur_id, caseid):

    customer = get_client_api(cur_id)
    if not customer:
        return response_error(f"Invalid Customer ID {cur_id}")

    return response_success(data=customer)


@manage_customers_blueprint.route('/manage/customers/update/<int:cur_id>/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator)
def view_customer_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_customers.manage_customers', cid=caseid))

    form = AddCustomerForm()
    customer = get_client(cur_id)
    if not customer:
        return response_error("Invalid Customer ID")

    form.customer_name.render_kw = {'value': customer.name}

    return render_template("modal_add_customer.html", form=form, customer=customer,
                           attributes=customer.custom_attributes)


@manage_customers_blueprint.route('/manage/customers/update/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def view_customers(cur_id, caseid):
    if not request.is_json:
        return response_error("Invalid request")

    try:
        client = update_client(cur_id, request.json)

    except ElementNotFoundException:
        return response_error('Invalid Customer ID')

    except ValidationError as e:
        return response_error("", data=e.messages)

    except Exception as e:
        print(traceback.format_exc())
        return response_error(f'An error occurred during Customer update. {e}')

    client_schema = CustomerSchema()
    return response_success("Customer updated", client_schema.dump(client))


@manage_customers_blueprint.route('/manage/customers/add/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator)
def add_customers_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_customers.manage_customers', cid=caseid))
    form = AddCustomerForm()
    attributes = get_default_custom_attributes('client')
    return render_template("modal_add_customer.html", form=form, customer=None, attributes=attributes)


@manage_customers_blueprint.route('/manage/customers/add', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def add_customers(caseid):
    if not request.is_json:
        return response_error("Invalid request")

    try:
        client = create_client(request.json)
    except ValidationError as e:
        return response_error(msg='Error adding customer', data=e.messages, status=400)
    except Exception as e:
        print(traceback.format_exc())
        return response_error(f'An error occurred during customer addition. {e}')

    track_activity(f"Added customer {client.name}", caseid=caseid, ctx_less=True)

    # Return the customer
    client_schema = CustomerSchema()
    return response_success("Added successfully", data=client_schema.dump(client))


@manage_customers_blueprint.route('/manage/customers/delete/<int:cur_id>', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def delete_customers(cur_id, caseid):
    try:

        delete_client(cur_id)

    except ElementNotFoundException:
        return response_error('Invalid Customer ID')

    except ElementInUseException:
        return response_error('Cannot delete a referenced customer')

    except Exception:
        return response_error('An error occurred during customer deletion')

    track_activity("Deleted Customer with ID {asset_id}".format(asset_id=cur_id), caseid=caseid, ctx_less=True)

    return response_success("Deleted successfully")
