#!/usr/bin/env python3
#
#
#  IRIS Source Code
#  Copyright (C) 2022 - DFIR IRIS Team
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
from flask import request

from app import db
from app.datamgmt.datastore.datastore_db import ds_list_tree
from app.models import DataStorePath
from app.util import api_login_required
from app.util import response_success

datastore_blueprint = Blueprint(
    'datastore',
    __name__,
    template_folder='templates'
)


@datastore_blueprint.route('/datastore/list/tree', methods=['GET'])
@api_login_required
def datastore_list_tree(caseid):

    data = ds_list_tree(caseid)

    return response_success("", data=data)


@datastore_blueprint.route('/datastore/push/tree', methods=['POST'])
@api_login_required
def datastore_push_tree(caseid: int):

    data = request.json

    for node in data:
        dsp = DataStorePath()
        dsp.path_is_root = node.get("is_root")
        dsp.path_name = node.get("name")
        dsp.path_parent_id = node.get("parent")
        dsp.path_case_id = caseid

        db.session.add(dsp)
        db.session.commit()

    return response_success("", data=data)