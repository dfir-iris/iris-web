#!/usr/bin/env python3
#
#  IRIS Source Code
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

from flask import Blueprint, Response

from app.datamgmt.alerts.alerts_db import get_alert_status_list, get_alert_status_by_id
from app.schema.marshables import AlertStatusSchema
from app.util import ac_api_requires
from app.util import response_success

manage_alerts_status_blueprint = Blueprint('manage_alerts_status',
                                           __name__,
                                           template_folder='templates')


# CONTENT ------------------------------------------------
@manage_alerts_status_blueprint.route('/manage/alert-status/list', methods=['GET'])
@ac_api_requires()
def list_alert_status(caseid: int) -> Response:
    """
    Get the list of alert status

    Args:
        caseid (int): case id

    Returns:
        Flask Response object
    """
    l_cl = get_alert_status_list()
    schema = AlertStatusSchema()

    return response_success("", data=schema.dump(l_cl, many=True))


@manage_alerts_status_blueprint.route('/manage/alert-status/<int:classification_id>', methods=['GET'])
@ac_api_requires()
def get_case_alert_status(status_id: int, caseid: int) -> Response:
    """
    Get the alert status

    Args:
        status_id (int): status id
        caseid (int): case id
    """
    cl = get_alert_status_by_id(status_id)
    schema = AlertStatusSchema()

    return response_success("", data=schema.dump(cl))
