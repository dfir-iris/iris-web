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

from flask import Blueprint, request

from app import db
from app.iris_engine.utils.tracker import track_activity
from app.models import IocType
from app.util import response_success, api_admin_required, response_error

from app.datamgmt.case.case_iocs_db import get_ioc_types_list, add_ioc_type
from app.util import api_login_required

manage_ioc_type_blueprint = Blueprint('manage_ioc_types',
                                      __name__,
                                      template_folder='templates')


# CONTENT ------------------------------------------------
@manage_ioc_type_blueprint.route('/manage/ioc-types/list', methods=['GET'])
@api_login_required
def list_ioc_types(caseid):
    lstatus = get_ioc_types_list()

    return response_success("", data=lstatus)


@manage_ioc_type_blueprint.route('/manage/ioc-type/add', methods=['POST'])
@api_admin_required
def add_ioc_type_api(caseid):
    if not request.is_json:
        return response_error("Invalid request")

    ioc_type_name = request.json.get('type_name')
    ioc_type_description = request.json.get('type_description')
    ioc_taxonomy = request.json.get('type_taxonomy')

    ioc_type = IocType.query.filter(IocType.type_name == ioc_type_name).first()
    if ioc_type:
        return response_error("An IOC type with this name already exists")

    ioct = add_ioc_type(name=ioc_type_name,
                        description=ioc_type_description,
                        taxonomy=ioc_taxonomy)

    track_activity("Added ioc type {ioc_type_name}".format(ioc_type_name=ioct.type_name), caseid=caseid, ctx_less=True)
    # Return the assets
    return response_success("Added successfully", data=ioct)


@manage_ioc_type_blueprint.route('/manage/ioc-type/delete/<int:cur_id>', methods=['GET'])
@api_admin_required
def remove_ioc_type(cur_id, caseid):
    if not request.is_json:
        return response_error("Invalid request")

    type_id = IocType.query.filter(
        IocType.type_id == cur_id
    ).first()

    if type_id:
        db.session.delete(type_id)
        track_activity("Deleted ioc type ID {type_id}".format(type_id=cur_id), caseid=caseid, ctx_less=True)
        return response_success("Deleted ioc type ID {type_id}".format(type_id=cur_id))

    track_activity("Attempted to delete ioc type ID {type_id}, but was not found".format(type_id=cur_id),
                    caseid=caseid, ctx_less=True)

    return response_error("Attempted to delete ioc type ID {type_id}, but was not found".format(type_id=cur_id))


