#!/usr/bin/env python3
#
#
#  IRIS Source Code
#  Copyright (C) 2022 - DFIR IRIS Team
#  contact@dfir-iris.org
#  Created by whitekernel - 2022-05-17
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

import marshmallow.exceptions
from flask import Blueprint
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from werkzeug.utils import redirect

from app import db
from app.datamgmt.datastore.datastore_db import datastore_add_child_node
from app.datamgmt.datastore.datastore_db import datastore_delete_file
from app.datamgmt.datastore.datastore_db import datastore_delete_node
from app.datamgmt.datastore.datastore_db import datastore_get_path_node
from app.datamgmt.datastore.datastore_db import datastore_get_standard_path
from app.datamgmt.datastore.datastore_db import datastore_rename_node
from app.datamgmt.datastore.datastore_db import ds_list_tree
from app.forms import ModalDSFileForm
from app.models import DataStoreFile
from app.models import DataStorePath
from app.schema.marshables import DSFileSchema
from app.util import api_login_required
from app.util import login_required
from app.util import response_error
from app.util import response_success
from app.util import add_obj_history_entry


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


@datastore_blueprint.route('/datastore/file/add/<int:cur_id>/modal', methods=['GET'])
@login_required
def datastore_add_file_modal(cur_id: int, caseid: int, url_redir: bool):

    if url_redir:
        return redirect(url_for('index.index', cid=caseid, redirect=True))

    dsp = datastore_get_path_node(cur_id, caseid)
    if not dsp:
        return response_error('Invalid path node for this case')

    form = ModalDSFileForm()

    return render_template("modal_ds_file.html", form=form, file=None, dsp=dsp)


@datastore_blueprint.route('/datastore/file/add/<int:cur_id>', methods=['POST'])
@api_login_required
def datastore_add_file(cur_id: int, caseid: int):

    dsp = datastore_get_path_node(cur_id, caseid)
    if not dsp:
        return response_error('Invalid path node for this case')

    dsf_schema = DSFileSchema()
    try:

        dsf_sc = dsf_schema.load(request.form, partial=True)

        dsf_sc.file_parent_id = dsp.path_id
        dsf_sc.added_by_user_id = current_user.id
        dsf_sc.file_date_added = datetime.datetime.now()
        dsf_sc.file_local_name = 'tmp_xc'
        dsf_sc.file_case_id = caseid
        add_obj_history_entry(dsf_sc, 'created')

        db.session.add(dsf_sc)
        db.session.commit()

        ds_location = datastore_get_standard_path(dsf_sc, caseid)
        dsf_schema.ds_store_file(request.files.get('file_content'), ds_location)

        dsf_sc.file_local_name = ds_location.as_posix()
        db.session.commit()

        return response_success('File saved in datastore')

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@datastore_blueprint.route('/datastore/folder/add', methods=['POST'])
@api_login_required
def datastore_add_folder(caseid: int):
    data = request.json
    if not data:
        return response_error('Invalid data')

    parent_node = data.get('parent_node')
    folder_name = data.get('folder_name')

    if not parent_node or not folder_name:
        return response_error('Invalid data')

    has_error, logs = datastore_add_child_node(parent_node, folder_name, caseid)

    return response_success(logs) if not has_error else response_error(logs)


@datastore_blueprint.route('/datastore/folder/rename/<int:cur_id>', methods=['POST'])
@api_login_required
def datastore_rename_folder(cur_id: int, caseid: int):
    data = request.json
    if not data:
        return response_error('Invalid data')

    parent_node = data.get('parent_node')
    folder_name = data.get('folder_name')

    if not parent_node or not folder_name:
        return response_error('Invalid data')

    if int(parent_node) != cur_id:
        return response_error('Invalid data')

    has_error, logs = datastore_rename_node(parent_node, folder_name, caseid)

    return response_success(logs) if not has_error else response_error(logs)


@datastore_blueprint.route('/datastore/folder/delete/<int:cur_id>', methods=['GET'])
@api_login_required
def datastore_delete_folder_route(cur_id: int, caseid: int):

    has_error, logs = datastore_delete_node(cur_id, caseid)

    return response_success(logs) if not has_error else response_error(logs)


@datastore_blueprint.route('/datastore/file/delete/<int:cur_id>', methods=['GET'])
@api_login_required
def datastore_delete_file_route(cur_id: int, caseid: int):

    has_error, logs = datastore_delete_file(cur_id, caseid)

    return response_success(logs) if not has_error else response_error(logs)


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


@datastore_blueprint.route('/datastore/push/file', methods=['POST'])
@api_login_required
def datastore_push_file(caseid: int):
    data = request.json

    for file in data:
        dsf = DataStoreFile()
        dsf.data_parent_id = file.get('parent')
        dsf.data_case_id = caseid
        dsf.added_by_user_id = current_user.id
        dsf.data_original_filename = file.get('name')
        dsf.data_local_filename = file.get('name')

        db.session.add(dsf)
        db.session.commit()

    return response_success("", data=data)