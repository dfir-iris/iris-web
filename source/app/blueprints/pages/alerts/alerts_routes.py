#  IRIS Source Code
#  Copyright (C) 2023 - DFIR-IRIS
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

from flask import Blueprint
from flask import render_template
from flask import redirect
from flask import url_for
from flask_wtf import FlaskForm
from typing import Union
from werkzeug import Response

from app.datamgmt.alerts.alerts_db import get_alert_by_id
from app.models.authorization import Permissions
from app.blueprints.responses import response_error
from app.blueprints.access_controls import ac_requires, ac_current_user_has_customer_access

alerts_blueprint = Blueprint(
    'alerts',
    __name__,
    template_folder='templates'
)


@alerts_blueprint.route('/alerts', methods=['GET'])
@ac_requires(Permissions.alerts_read, no_cid_required=True)
def alerts_list_view_route(caseid, url_redir) -> Union[str, Response]:
    """
    List all alerts

    args:
        caseid (str): The case id

    returns:
        Response: The response
    """
    if url_redir:
        return redirect(url_for('alerts.alerts_list_view_route', cid=caseid))

    form = FlaskForm()

    return render_template('alerts.html', caseid=caseid, form=form)


@alerts_blueprint.route('/alerts/<int:cur_id>/comments/modal', methods=['GET'])
@ac_requires(Permissions.alerts_read, no_cid_required=True)
def alert_comment_modal(cur_id, caseid, url_redir):
    """
    Get the modal for the alert comments

    args:
        cur_id (int): The alert id
        caseid (str): The case id

    returns:
        Response: The response
    """
    if url_redir:
        return redirect(url_for('alerts.alerts_list_view_route', cid=caseid, redirect=True))

    alert = get_alert_by_id(cur_id)
    if not alert:
        return response_error('Invalid alert ID')

    if not ac_current_user_has_customer_access(alert.alert_customer_id):
        return response_error('User not entitled to update alerts for the client', status=403)

    return render_template("modal_conversation.html", element_id=cur_id, element_type='alerts',
                           title=f" alert #{alert.alert_id}")
