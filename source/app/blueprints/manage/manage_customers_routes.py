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

from flask import Blueprint
from flask import render_template, request, url_for, redirect
from marshmallow import ValidationError

from app.datamgmt.client.client_db import get_client_list, get_client, update_client, create_client, delete_client
from app.datamgmt.exceptions.ElementExceptions import ElementNotFoundException, ElementInUseException
from app.forms import AddCustomerForm
from app.iris_engine.utils.tracker import track_activity
from app.util import response_success, response_error, login_required, admin_required, api_admin_required
from app.schema.marshables import CustomerSchema

manage_customers_blueprint = Blueprint(
    'manage_customers',
    __name__,
    template_folder='templates'
)


# CONTENT ------------------------------------------------
@manage_customers_blueprint.route('/manage/customers')
@admin_required
def manage_customers(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_customers.manage_customers', cid=caseid))

    form = AddCustomerForm()

    # Return default page of case management
    return render_template('manage_customers.html', form=form)


@manage_customers_blueprint.route('/manage/customers/list')
@api_admin_required
def list_customers(caseid):
    client_list = get_client_list(is_api=True)

    return response_success("", data=client_list)


@manage_customers_blueprint.route('/manage/customers/update/<int:cur_id>/modal', methods=['GET'])
@login_required
def view_customer_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_customers.manage_customers', cid=caseid))

    form = AddCustomerForm()
    customer = get_client(cur_id)
    if not customer:
        response_error("Invalid Customer ID")

    form.customer_name.render_kw = {'value': customer.name}

    return render_template("modal_add_customer.html", form=form, customer=customer)


@manage_customers_blueprint.route('/manage/customers/update/<int:cur_id>', methods=['POST'])
@api_admin_required
def view_customers(cur_id, caseid):
    if not request.is_json:
        return response_error("Invalid request")

    try:
        update_client(cur_id, request.json.get('customer_name'))
    except ElementNotFoundException:
        return response_error('Invalid Customer ID')
    except ValidationError as e:
        return response_error(str(e))
    except Exception:
        return response_error('An error occurred during Customer update ...')

    return response_success("Customer updated")


@manage_customers_blueprint.route('/manage/customers/add/modal', methods=['GET'])
@admin_required
def add_customers_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_customers.manage_customers', cid=caseid))
    form = AddCustomerForm()

    return render_template("modal_add_customer.html", form=form, customer=None)


@manage_customers_blueprint.route('/manage/customers/add', methods=['POST'])
@api_admin_required
def add_customers(caseid):
    if not request.is_json:
        return response_error("Invalid request")

    try:
        client = create_client(request.json.get('customer_name'))
    except ValidationError as e:
        return response_error(msg='Error adding customer', data=e.messages, status=400)
    except Exception:
        return response_error('An error occurred during customer addition')

    track_activity(f"Added customer {client.name}", caseid=caseid, ctx_less=True)

    # Return the customer
    client_schema = CustomerSchema()
    return response_success("Added successfully", data=client_schema.dump(client))


@manage_customers_blueprint.route('/manage/customers/delete/<int:cur_id>', methods=['GET'])
@api_admin_required
def delete_customers(cur_id, caseid):
    try:
        delete_client(cur_id)
    except ElementNotFoundException:
        return response_error('Invalid Customer ID')
    except ElementInUseException:
        return response_error('Cannot delete a referenced customer')
    except Exception:
        return response_error('An error occurred during customer deletion ...')

    track_activity("Deleted Customer with ID {asset_id}".format(asset_id=cur_id), caseid=caseid, ctx_less=True)

    return response_success("Deleted successfully")
