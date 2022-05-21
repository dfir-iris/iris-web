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
from flask import send_file
from flask import url_for
from flask_login import current_user
from werkzeug.utils import redirect

from app import db
from app.datamgmt.datastore.datastore_db import datastore_add_child_node
from app.datamgmt.datastore.datastore_db import datastore_add_file_as_evidence
from app.datamgmt.datastore.datastore_db import datastore_add_file_as_ioc
from app.datamgmt.datastore.datastore_db import datastore_delete_file
from app.datamgmt.datastore.datastore_db import datastore_delete_node
from app.datamgmt.datastore.datastore_db import datastore_get_file
from app.datamgmt.datastore.datastore_db import datastore_get_local_file_path
from app.datamgmt.datastore.datastore_db import datastore_get_path_node
from app.datamgmt.datastore.datastore_db import datastore_get_standard_path
from app.datamgmt.datastore.datastore_db import datastore_rename_node
from app.datamgmt.datastore.datastore_db import ds_list_tree
from app.forms import ModalDSFileForm
from app.schema.marshables import DSFileSchema
from app.util import add_obj_history_entry
from app.util import api_login_required
from app.util import login_required
from app.util import response_error
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


@datastore_blueprint.route('/datastore/file/update/<int:cur_id>/modal', methods=['GET'])
@login_required
def datastore_update_file_modal(cur_id: int, caseid: int, url_redir: bool):

    if url_redir:
        return redirect(url_for('index.index', cid=caseid, redirect=True))

    file = datastore_get_file(cur_id, caseid)
    if not file:
        return response_error('Invalid file ID for this case')

    dsp = datastore_get_path_node(file.file_parent_id, caseid)

    form = ModalDSFileForm()
    form.file_is_ioc.data = file.file_is_ioc
    form.file_original_name.data = file.file_original_name
    form.file_password.data = file.file_password
    form.file_description.data = file.file_description
    form.file_is_evidence.data = file.file_is_evidence

    return render_template("modal_ds_file.html", form=form, file=file, dsp=dsp)


@datastore_blueprint.route('/datastore/file/info/<int:cur_id>/modal', methods=['GET'])
@login_required
def datastore_info_file_modal(cur_id: int, caseid: int, url_redir: bool):

    if url_redir:
        return redirect(url_for('index.index', cid=caseid, redirect=True))

    file = datastore_get_file(cur_id, caseid)
    if not file:
        return response_error('Invalid file ID for this case')

    dsp = datastore_get_path_node(file.file_parent_id, caseid)

    return render_template("modal_ds_file_info.html", file=file, dsp=dsp)


@datastore_blueprint.route('/datastore/file/update/<int:cur_id>', methods=['POST'])
@api_login_required
def datastore_update_file(cur_id: int, caseid: int):

    dsf = datastore_get_file(cur_id, caseid)
    if not dsf:
        return response_error('Invalid file ID for this case')

    dsf_schema = DSFileSchema()
    try:

        dsf_sc = dsf_schema.load(request.form, instance=dsf, partial=True)
        add_obj_history_entry(dsf_sc, 'updated')

        dsf.file_is_ioc = request.form.get('file_is_ioc') is not None or request.form.get('file_is_ioc') is True
        dsf.file_is_evidence = request.form.get('file_is_evidence') is not None or request.form.get('file_is_evidence') is True

        db.session.commit()

        if request.files.get('file_content'):
            ds_location = datastore_get_standard_path(dsf_sc, caseid)
            dsf_sc.file_local_name, dsf_sc.file_size, dsf_sc.file_sha256 = dsf_schema.ds_store_file(
                request.files.get('file_content'),
                ds_location,
                dsf_sc.file_is_ioc,
                dsf_sc.file_password)

            db.session.commit()

        msg_added_as = ''
        if dsf.file_is_ioc:
            datastore_add_file_as_ioc(dsf, caseid)
            msg_added_as += 'and added in IOC'

        if dsf.file_is_evidence:
            datastore_add_file_as_evidence(dsf, caseid)
            msg_added_as += ' and evidence' if len(msg_added_as) > 0 else 'and added in evidence'

        return response_success('File updated in datastore')

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@datastore_blueprint.route('/datastore/file/move/<int:cur_id>', methods=['POST'])
@api_login_required
def datastore_move_file(cur_id: int, caseid: int):

    if not request.json:
        return response_error("Invalid data")

    dsf = datastore_get_file(cur_id, caseid)
    if not dsf:
        return response_error('Invalid file ID for this case')

    dsp = datastore_get_path_node(request.json.get('destination-node'), caseid)
    if not dsp:
        return response_error('Invalid destination node ID for this case')

    dsf.file_parent_id = dsp.path_id
    db.session.commit()

    return response_success(f"File successfully moved to {dsp.path_name}")


@datastore_blueprint.route('/datastore/folder/move/<int:cur_id>', methods=['POST'])
@api_login_required
def datastore_move_folder(cur_id: int, caseid: int):

    if not request.json:
        return response_error("Invalid data")

    dsp = datastore_get_path_node(cur_id, caseid)
    if not dsp:
        return response_error('Invalid file ID for this case')

    dsp_dst = datastore_get_path_node(request.json.get('destination-node'), caseid)
    if not dsp_dst:
        return response_error('Invalid destination node ID for this case')

    if dsp.path_id == dsp_dst.path_id:
        return response_error("If that's true, then I've made a mistake, and you should kill me now.")

    dsp.path_parent_id = dsp_dst.path_id
    db.session.commit()

    return response_success(f"Folder {dsp.path_name} successfully moved to {dsp_dst.path_name}")


@datastore_blueprint.route('/datastore/file/view/<int:cur_id>', methods=['GET'])
@api_login_required
def datastore_view_file(cur_id: int, caseid: int):
    has_error, dsf = datastore_get_local_file_path(cur_id, caseid)
    if has_error:
        return response_error('Unable to get request file ID', data=dsf)

    resp = send_file(dsf.file_local_name, as_attachment=True,
                     attachment_filename=dsf.file_original_name)

    return resp


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
        dsf_sc.file_local_name, dsf_sc.file_size, dsf_sc.file_sha256 = dsf_schema.ds_store_file(
            request.files.get('file_content'),
            ds_location,
            dsf_sc.file_is_ioc,
            dsf_sc.file_password)

        db.session.commit()

        msg_added_as = ''
        if dsf_sc.file_is_ioc:
            datastore_add_file_as_ioc(dsf_sc, caseid)
            msg_added_as += 'and added in IOC'

        if dsf_sc.file_is_evidence:
            datastore_add_file_as_evidence(dsf_sc, caseid)
            msg_added_as += ' and evidence' if len(msg_added_as) > 0 else 'and added in evidence'

        return response_success(f'File saved in datastore {msg_added_as}')

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
