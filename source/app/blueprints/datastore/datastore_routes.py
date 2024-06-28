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
import base64
import datetime
import json
import marshmallow.exceptions
import urllib.parse
from flask import Blueprint
from flask import render_template
from flask import request
from flask import send_file
from flask import url_for
from flask_login import current_user
from pathlib import Path
from werkzeug.utils import redirect

import app
from app import db
from app.datamgmt.datastore.datastore_db import datastore_add_child_node
from app.datamgmt.datastore.datastore_db import datastore_add_file_as_evidence
from app.datamgmt.datastore.datastore_db import datastore_add_file_as_ioc
from app.datamgmt.datastore.datastore_db import datastore_delete_file
from app.datamgmt.datastore.datastore_db import datastore_delete_node
from app.datamgmt.datastore.datastore_db import datastore_filter_tree
from app.datamgmt.datastore.datastore_db import datastore_get_file
from app.datamgmt.datastore.datastore_db import datastore_get_interactive_path_node
from app.datamgmt.datastore.datastore_db import datastore_get_local_file_path
from app.datamgmt.datastore.datastore_db import datastore_get_path_node
from app.datamgmt.datastore.datastore_db import datastore_get_standard_path
from app.datamgmt.datastore.datastore_db import datastore_rename_node
from app.datamgmt.datastore.datastore_db import ds_list_tree
from app.forms import ModalDSFileForm
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import DSFileSchema, DSPathSchema
from app.util import ac_api_case_requires
from app.util import ac_case_requires
from app.util import add_obj_history_entry
from app.util import response_error
from app.util import response_success

datastore_blueprint = Blueprint(
    'datastore',
    __name__,
    template_folder='templates'
)

logger = app.logger


@datastore_blueprint.route('/datastore/list/tree', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def datastore_list_tree(caseid):

    data = ds_list_tree(caseid)

    return response_success("", data=data)


@datastore_blueprint.route('/datastore/list/filter', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def datastore_list_filter(caseid):

    args = request.args.to_dict()
    query_filter = args.get('q')
    try:

        filter_d = dict(json.loads(urllib.parse.unquote_plus(query_filter)))

    except Exception as e:
        logger.error('Error parsing filter: {}'.format(query_filter))
        logger.error(e)
        return response_error('Invalid query')

    data, log = datastore_filter_tree(filter_d, caseid)
    if data is None:
        logger.error('Error parsing filter: {}'.format(query_filter))
        logger.error(log)
        return response_error('Invalid query')

    return response_success("", data=data)


@datastore_blueprint.route('/datastore/file/add/<int:cur_id>/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.full_access)
def datastore_add_file_modal(cur_id: int, caseid: int, url_redir: bool):

    if url_redir:
        return redirect(url_for('index.index', cid=caseid, redirect=True))

    dsp = datastore_get_path_node(cur_id, caseid)
    if not dsp:
        return response_error('Invalid path node for this case')

    form = ModalDSFileForm()

    return render_template("modal_ds_file.html", form=form, file=None, dsp=dsp)


@datastore_blueprint.route('/datastore/file/add/<int:cur_id>/multi-modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.full_access)
def datastore_add_multi_files_modal(cur_id: int, caseid: int, url_redir: bool):

    if url_redir:
        return redirect(url_for('index.index', cid=caseid, redirect=True))

    dsp = datastore_get_path_node(cur_id, caseid)
    if not dsp:
        return response_error('Invalid path node for this case')

    form = ModalDSFileForm()

    return render_template("modal_ds_multi_files.html", form=form, file=None, dsp=dsp)


@datastore_blueprint.route('/datastore/filter-help/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def datastore_filter_help_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('index.index', cid=caseid, redirect=True))

    return render_template("modal_help_filter_ds.html")


@datastore_blueprint.route('/datastore/file/update/<int:cur_id>/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
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
    form.file_password.render_kw = {'disabled': 'disabled'}
    form.file_description.data = file.file_description
    form.file_is_evidence.data = file.file_is_evidence

    return render_template("modal_ds_file.html", form=form, file=file, dsp=dsp)


@datastore_blueprint.route('/datastore/file/info/<int:cur_id>/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def datastore_info_file_modal(cur_id: int, caseid: int, url_redir: bool):

    if url_redir:
        return redirect(url_for('index.index', cid=caseid, redirect=True))

    file = datastore_get_file(cur_id, caseid)
    if not file:
        return response_error('Invalid file ID for this case')

    dsp = datastore_get_path_node(file.file_parent_id, caseid)

    return render_template("modal_ds_file_info.html", file=file, dsp=dsp)


@datastore_blueprint.route('/datastore/file/info/<int:cur_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def datastore_info_file(cur_id: int, caseid: int):

    file = datastore_get_file(cur_id, caseid)
    if not file:
        return response_error('Invalid file ID for this case')

    file_schema = DSFileSchema()
    file = file_schema.dump(file)
    del file['file_local_name']

    return response_success("", data=file)


@datastore_blueprint.route('/datastore/file/update/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
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

            if dsf_sc.file_is_ioc and not dsf_sc.file_password:
                dsf_sc.file_password = 'infected'

            db.session.commit()

        msg_added_as = ''
        if dsf.file_is_ioc:
            datastore_add_file_as_ioc(dsf, caseid)
            msg_added_as += 'and added in IOC'

        if dsf.file_is_evidence:
            datastore_add_file_as_evidence(dsf, caseid)
            msg_added_as += ' and evidence' if len(msg_added_as) > 0 else 'and added in evidence'

        track_activity(f'File \"{dsf.file_original_name}\" updated in DS', caseid=caseid)
        return response_success('File updated in datastore', data=dsf_schema.dump(dsf_sc))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@datastore_blueprint.route('/datastore/file/move/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
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

    track_activity(f'File \"{dsf.file_original_name}\" moved to \"{dsp.path_name}\" in DS', caseid=caseid)
    return response_success(f"File successfully moved to {dsp.path_name}")


@datastore_blueprint.route('/datastore/folder/move/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
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

    dsf_folder_schema = DSPathSchema()

    msg = f"Folder \"{dsp.path_name}\" successfully moved to \"{dsp_dst.path_name}\""
    track_activity(msg, caseid=caseid)
    return response_success(msg, data=dsf_folder_schema.dump(dsp))


@datastore_blueprint.route('/datastore/file/view/<int:cur_id>', methods=['GET'])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def datastore_view_file(cur_id: int, caseid: int):
    has_error, dsf = datastore_get_local_file_path(cur_id, caseid)
    if has_error:
        return response_error('Unable to get requested file ID', data=dsf)

    if dsf.file_is_ioc or dsf.file_password:
        destination_name = dsf.file_original_name + ".zip"
    else:
        destination_name = dsf.file_original_name

    if not Path(dsf.file_local_name).is_file():
        return response_error(f'File {dsf.file_local_name} does not exists on the server. '
                              f'Update or delete virtual entry')

    resp = send_file(dsf.file_local_name, as_attachment=False,
                     download_name=destination_name)

    track_activity(f"File \"{destination_name}\" downloaded", caseid=caseid, display_in_ui=False)
    return resp


@datastore_blueprint.route('/datastore/file/add/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
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

        if dsf_sc.file_is_ioc and not dsf_sc.file_password:
            dsf_sc.file_password = 'infected'

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

        track_activity(f"File \"{dsf_sc.file_original_name}\" added to DS", caseid=caseid)
        return response_success(f'File saved in datastore {msg_added_as}', data=dsf_schema.dump(dsf_sc))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@datastore_blueprint.route('/datastore/file/add-interactive', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def datastore_add_interactive_file(caseid: int):

    dsp = datastore_get_interactive_path_node(caseid)
    if not dsp:
        return response_error('Invalid path node for this case')

    dsf_schema = DSFileSchema()
    try:
        js_data = request.json

        try:
            file_content = base64.b64decode(js_data.get('file_content'))
            filename = js_data.get('file_original_name')
        except Exception as e:
            return response_error(msg=str(e))

        dsf_sc, existed = dsf_schema.ds_store_file_b64(filename, file_content, dsp, caseid)

        if not existed:
            msg = "File saved in datastore"

        else:
            msg = "File already existing in datastore. Using it."

        track_activity(f"File \"{dsf_sc.file_original_name}\" added to DS", caseid=caseid)
        return response_success(msg, data={"file_url": f"/datastore/file/view/{dsf_sc.file_id}"})

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)


@datastore_blueprint.route('/datastore/folder/add', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def datastore_add_folder(caseid: int):
    data = request.json
    if not data:
        return response_error('Invalid data')

    parent_node = data.get('parent_node')
    folder_name = data.get('folder_name')

    if not parent_node or not folder_name:
        return response_error('Invalid data')

    has_error, logs, node = datastore_add_child_node(parent_node, folder_name, caseid)
    dsf_folder_schema = DSPathSchema()

    if not has_error:
        track_activity(f"Folder \"{folder_name}\" added to DS", caseid=caseid)
        return response_success(msg=logs, data=dsf_folder_schema.dump(node))

    return response_error(msg=logs)


@datastore_blueprint.route('/datastore/folder/rename/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
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

    has_error, logs, dsp_base = datastore_rename_node(parent_node, folder_name, caseid)
    dsf_folder_schema = DSPathSchema()

    if has_error:
        return response_error(logs)

    track_activity(f"Folder \"{parent_node}\" renamed to \"{folder_name}\" in DS", caseid=caseid)
    return response_success(logs, data=dsf_folder_schema.dump(dsp_base))


@datastore_blueprint.route('/datastore/folder/delete/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def datastore_delete_folder_route(cur_id: int, caseid: int):

    has_error, logs = datastore_delete_node(cur_id, caseid)
    if has_error:
        return response_error(logs)

    track_activity(f"Folder \"{cur_id}\" deleted from DS", caseid=caseid)
    return response_success(logs)


@datastore_blueprint.route('/datastore/file/delete/<int:cur_id>', methods=['POST'])
@ac_api_case_requires(CaseAccessLevel.full_access)
def datastore_delete_file_route(cur_id: int, caseid: int):

    has_error, logs = datastore_delete_file(cur_id, caseid)
    if has_error:
        return response_error(logs)

    track_activity(f"File \"{cur_id}\" deleted from DS", caseid=caseid)
    return response_success(logs)
