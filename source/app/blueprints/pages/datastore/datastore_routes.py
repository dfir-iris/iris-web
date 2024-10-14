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
from flask import render_template
from flask import url_for
from werkzeug.utils import redirect

from app.datamgmt.datastore.datastore_db import datastore_get_file
from app.datamgmt.datastore.datastore_db import datastore_get_path_node
from app.forms import ModalDSFileForm
from app.models.authorization import CaseAccessLevel
from app.blueprints.access_controls import ac_case_requires
from app.blueprints.responses import response_error

datastore_blueprint = Blueprint(
    'datastore',
    __name__,
    template_folder='templates'
)


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
