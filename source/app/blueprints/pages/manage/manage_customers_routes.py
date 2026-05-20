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

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import url_for
from flask_wtf import FlaskForm

from app.datamgmt.client.client_db import get_customer
from app.datamgmt.client.client_db import get_client_api
from app.datamgmt.client.client_db import get_client_contact
from app.datamgmt.client.client_db import get_client_contacts
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.forms import AddCustomerForm
from app.forms import ContactForm
from app.models.authorization import Permissions
from app.schema.marshables import ContactSchema
from app.blueprints.access_controls import ac_requires
from app.blueprints.access_controls import ac_requires_client_access
from app.blueprints.responses import page_not_found
from app.blueprints.responses import response_error

manage_customers_blueprint = Blueprint(
    'manage_customers',
    __name__,
    template_folder='templates'
)


@manage_customers_blueprint.route('/manage/customers')
@ac_requires(Permissions.customers_read, no_cid_required=True)
def manage_customers(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_customers.manage_customers', cid=caseid))

    form = AddCustomerForm()

    # Return default page of case management
    return render_template('manage_customers.html', form=form)


@manage_customers_blueprint.route('/manage/customers/<int:client_id>/view', methods=['GET'])
@ac_requires(Permissions.customers_read, no_cid_required=True)
@ac_requires_client_access()
def view_customer_page(client_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_customers.manage_customers', cid=caseid))

    customer = get_client_api(client_id)
    if not customer:
        return page_not_found(None)

    form = FlaskForm()
    contacts = get_client_contacts(client_id)
    contacts = ContactSchema().dump(contacts, many=True)

    return render_template('manage_customer_view.html', customer=customer, form=form, contacts=contacts)


@manage_customers_blueprint.route('/manage/customers/<int:client_id>/contacts/add/modal', methods=['GET'])
@ac_requires(Permissions.customers_write, no_cid_required=True)
@ac_requires_client_access()
def customer_add_contact_modal(client_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_customers.manage_customers', cid=caseid))

    form = ContactForm()

    return render_template('modal_customer_add_contact.html', form=form, contact=None)


@manage_customers_blueprint.route('/manage/customers/<int:client_id>/contacts/<int:contact_id>/modal', methods=['GET'])
@ac_requires(Permissions.customers_read, no_cid_required=True)
@ac_requires_client_access()
def customer_edit_contact_modal(client_id, contact_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_customers.manage_customers', cid=caseid))

    contact = get_client_contact(contact_id)
    if not contact:
        return response_error(f"Invalid Contact ID {contact_id}")

    form = ContactForm()
    form.contact_name.render_kw = {'value': contact.contact_name}
    form.contact_email.render_kw = {'value':  contact.contact_email}
    form.contact_mobile_phone.render_kw = {'value': contact.contact_mobile_phone}
    form.contact_work_phone.render_kw = {'value': contact.contact_work_phone}
    form.contact_note.data = contact.contact_note
    form.contact_role.render_kw = {'value':  contact.contact_role}

    return render_template('modal_customer_add_contact.html', form=form, contact=contact)


@manage_customers_blueprint.route('/manage/customers/update/<int:client_id>/modal', methods=['GET'])
@ac_requires(Permissions.customers_read, no_cid_required=True)
@ac_requires_client_access()
def view_customer_modal(client_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_customers.manage_customers', cid=caseid))

    form = AddCustomerForm()
    customer = get_customer(client_id)
    if not customer:
        return response_error("Invalid Customer ID")

    form.customer_name.render_kw = {'value': customer.name}
    form.customer_description.data = customer.description
    form.customer_sla.data = customer.sla

    return render_template("modal_add_customer.html", form=form, customer=customer,
                           attributes=customer.custom_attributes)


@manage_customers_blueprint.route('/manage/customers/add/modal', methods=['GET'])
@ac_requires(Permissions.customers_read, no_cid_required=True)
def add_customers_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_customers.manage_customers', cid=caseid))
    form = AddCustomerForm()
    attributes = get_default_custom_attributes('client')
    return render_template("modal_add_customer.html", form=form, customer=None, attributes=attributes)
