#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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
import marshmallow.exceptions
from flask import Blueprint
from flask import request
from flask import send_file
from pathlib import Path

from app.db import db
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.business.cases import cases_exists
from app.datamgmt.datastore.datastore_db import datastore_add_child_node
from app.datamgmt.datastore.datastore_db import datastore_add_file_as_evidence
from app.datamgmt.datastore.datastore_db import datastore_add_file_as_ioc
from app.datamgmt.datastore.datastore_db import datastore_delete_file
from app.datamgmt.datastore.datastore_db import datastore_delete_node
from app.datamgmt.datastore.datastore_db import datastore_get_file
from app.datamgmt.datastore.datastore_db import datastore_get_interactive_path_node
from app.datamgmt.datastore.datastore_db import datastore_get_local_file_path
from app.datamgmt.datastore.datastore_db import datastore_get_path_node
from app.datamgmt.datastore.datastore_db import datastore_get_standard_path
from app.datamgmt.datastore.datastore_db import datastore_rename_node
from app.datamgmt.datastore.datastore_db import ds_list_tree
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.models.models import DataStoreFile
from app.models.models import DataStorePath
from app.schema.marshables import DSFileSchema
from app.schema.marshables import DSPathSchema
from app.util import add_obj_history_entry


_READ_LEVELS = [CaseAccessLevel.read_only, CaseAccessLevel.full_access]
_WRITE_LEVELS = [CaseAccessLevel.full_access]


def _check_case_access(case_identifier, access_levels):
    if not cases_exists(case_identifier):
        return response_api_not_found()
    if not ac_fast_check_current_user_has_case_access(case_identifier, access_levels):
        return ac_api_return_access_denied(caseid=case_identifier)
    return None


def _truthy(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


# Allowlist of multipart form fields a caller may write through the file
# add/update endpoints. Anything else (notably file_id, file_local_name,
# file_case_id, file_sha256, file_size, added_by_user_id, file_date_added,
# ...) is dropped before the schema is loaded. Closes the mass-assignment
# vector reported as GHSA-qhqj-8qw6-wp8v / CWE-915.
_DS_FILE_WRITABLE_FIELDS = (
    'file_original_name',
    'file_description',
    'file_password',
    'file_is_ioc',
    'file_is_evidence',
    'file_parent_id',
)


def _filter_ds_file_form(form):
    return {field: form.get(field) for field in _DS_FILE_WRITABLE_FIELDS if field in form}


class DatastoreOperations:
    """Case-scoped datastore operations exposed via the v2 API.

    Mirrors the legacy `/datastore/...` blueprint feature-for-feature so the
    new frontend can manage the per-case file tree without falling back to v1
    endpoints. Folder operations are JSON; file operations accept multipart
    form data because they carry an uploaded file alongside metadata.
    """

    def __init__(self):
        self._file_schema = DSFileSchema()
        self._path_schema = DSPathSchema()

    # ---------------------------------------------------------------------
    # Tree
    # ---------------------------------------------------------------------
    def tree(self, case_identifier):
        access_error = _check_case_access(case_identifier, _READ_LEVELS)
        if access_error:
            return access_error

        return response_api_success(ds_list_tree(case_identifier))

    # ---------------------------------------------------------------------
    # File list (flat, paginated). The legacy UI rendered the whole tree at
    # once; the new UI also wants a paginated flat view so the data-table
    # mode can lazy-load like every other case section.
    # ---------------------------------------------------------------------
    def list_files(self, case_identifier):
        access_error = _check_case_access(case_identifier, _READ_LEVELS)
        if access_error:
            return access_error

        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 25))
        except (TypeError, ValueError):
            return response_api_error('Invalid pagination parameters')

        order_by = request.args.get('order_by', 'file_date_added')
        sort_dir = request.args.get('sort_dir', 'desc').lower()
        order_column = getattr(DataStoreFile, order_by, None)
        if order_column is None:
            return response_api_error(f'Invalid order_by field: {order_by}')

        query = DataStoreFile.query.filter(DataStoreFile.file_case_id == case_identifier)
        query = query.order_by(order_column.desc() if sort_dir == 'desc' else order_column.asc())

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        return response_api_success({
            'total': paginated.total,
            'data': self._file_schema.dump(paginated.items, many=True),
            'last_page': paginated.pages,
            'current_page': paginated.page,
            'next_page': paginated.next_num if paginated.has_next else None
        })

    # ---------------------------------------------------------------------
    # File CRUD
    # ---------------------------------------------------------------------
    def get_file_info(self, case_identifier, identifier):
        access_error = _check_case_access(case_identifier, _READ_LEVELS)
        if access_error:
            return access_error

        dsf = datastore_get_file(identifier, case_identifier)
        if not dsf:
            return response_api_not_found()

        data = self._file_schema.dump(dsf)
        data.pop('file_local_name', None)
        return response_api_success(data)

    def view_file(self, case_identifier, identifier):
        access_error = _check_case_access(case_identifier, _READ_LEVELS)
        if access_error:
            return access_error

        if not datastore_get_file(identifier, case_identifier):
            return response_api_not_found()

        has_error, dsf = datastore_get_local_file_path(identifier, case_identifier)
        if has_error:
            return response_api_error('Unable to get requested file ID', data=dsf)

        if dsf.file_is_ioc or dsf.file_password:
            destination_name = dsf.file_original_name + '.zip'
        else:
            destination_name = dsf.file_original_name

        if not Path(dsf.file_local_name).is_file():
            return response_api_error(
                f'File {dsf.file_local_name} does not exist on the server. '
                f'Update or delete virtual entry'
            )

        # Keep inline display only for file types the browser cannot execute
        # as script. SVG can embed <script>; HTML/XML execute JS in the
        # application origin. Force everything else to download so a
        # malicious upload can't turn the datastore into a stored-XSS sink
        # (SBA-ADV-20260126-03 / CWE-79).
        safe_inline_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}
        file_extension = Path(destination_name).suffix.lower().lstrip('.')
        serve_as_attachment = file_extension not in safe_inline_extensions

        resp = send_file(dsf.file_local_name, as_attachment=serve_as_attachment, download_name=destination_name)

        track_activity(
            f'File "{destination_name}" downloaded',
            caseid=case_identifier,
            display_in_ui=False
        )
        return resp

    def add_file(self, case_identifier, folder_identifier):
        access_error = _check_case_access(case_identifier, _WRITE_LEVELS)
        if access_error:
            return access_error

        dsp = datastore_get_path_node(folder_identifier, case_identifier)
        if not dsp:
            return response_api_not_found()

        try:
            dsf_sc = self._file_schema.load(_filter_ds_file_form(request.form), partial=True)

            dsf_sc.file_parent_id = dsp.path_id
            dsf_sc.added_by_user_id = iris_current_user.id
            dsf_sc.file_date_added = datetime.datetime.now()
            dsf_sc.file_local_name = 'tmp_xc'
            dsf_sc.file_case_id = case_identifier
            dsf_sc.file_is_ioc = _truthy(request.form.get('file_is_ioc'))
            dsf_sc.file_is_evidence = _truthy(request.form.get('file_is_evidence'))
            add_obj_history_entry(dsf_sc, 'created')

            if dsf_sc.file_is_ioc and not dsf_sc.file_password:
                dsf_sc.file_password = 'infected'

            db.session.add(dsf_sc)
            db.session.commit()

            uploaded = request.files.get('file_content')
            if not uploaded:
                db.session.delete(dsf_sc)
                db.session.commit()
                return response_api_error('Missing file content')

            ds_location = datastore_get_standard_path(dsf_sc, case_identifier)
            dsf_sc.file_local_name, dsf_sc.file_size, dsf_sc.file_sha256 = self._file_schema.ds_store_file(
                uploaded,
                ds_location,
                dsf_sc.file_is_ioc,
                dsf_sc.file_password
            )
            db.session.commit()

            if dsf_sc.file_is_ioc:
                datastore_add_file_as_ioc(iris_current_user.id, dsf_sc)
            if dsf_sc.file_is_evidence:
                datastore_add_file_as_evidence(iris_current_user.id, dsf_sc, case_identifier)

            track_activity(
                f'File "{dsf_sc.file_original_name}" added to DS',
                caseid=case_identifier
            )
            return response_api_created(self._file_schema.dump(dsf_sc))

        except marshmallow.exceptions.ValidationError as e:
            return response_api_error('Data error', data=e.messages)

    def update_file(self, case_identifier, identifier):
        access_error = _check_case_access(case_identifier, _WRITE_LEVELS)
        if access_error:
            return access_error

        dsf = datastore_get_file(identifier, case_identifier)
        if not dsf:
            return response_api_not_found()

        try:
            dsf_sc = self._file_schema.load(_filter_ds_file_form(request.form), instance=dsf, partial=True)
            add_obj_history_entry(dsf_sc, 'updated')

            if 'file_is_ioc' in request.form:
                dsf.file_is_ioc = _truthy(request.form.get('file_is_ioc'))
            if 'file_is_evidence' in request.form:
                dsf.file_is_evidence = _truthy(request.form.get('file_is_evidence'))

            db.session.commit()

            uploaded = request.files.get('file_content')
            if uploaded:
                ds_location = datastore_get_standard_path(dsf_sc, case_identifier)
                dsf_sc.file_local_name, dsf_sc.file_size, dsf_sc.file_sha256 = self._file_schema.ds_store_file(
                    uploaded,
                    ds_location,
                    dsf_sc.file_is_ioc,
                    dsf_sc.file_password
                )
                if dsf_sc.file_is_ioc and not dsf_sc.file_password:
                    dsf_sc.file_password = 'infected'
                db.session.commit()

            if dsf.file_is_ioc:
                datastore_add_file_as_ioc(iris_current_user.id, dsf)
            if dsf.file_is_evidence:
                datastore_add_file_as_evidence(iris_current_user.id, dsf, case_identifier)

            track_activity(
                f'File "{dsf.file_original_name}" updated in DS',
                caseid=case_identifier
            )
            return response_api_success(self._file_schema.dump(dsf_sc))

        except marshmallow.exceptions.ValidationError as e:
            return response_api_error('Data error', data=e.messages)

    def move_file(self, case_identifier, identifier):
        access_error = _check_case_access(case_identifier, _WRITE_LEVELS)
        if access_error:
            return access_error

        dsf = datastore_get_file(identifier, case_identifier)
        if not dsf:
            return response_api_not_found()

        data = request.get_json() or {}
        destination = data.get('destination_node')
        if destination is None:
            return response_api_error('Missing destination_node')

        dsp = datastore_get_path_node(destination, case_identifier)
        if not dsp:
            return response_api_error('Invalid destination node ID for this case')

        dsf.file_parent_id = dsp.path_id
        db.session.commit()

        track_activity(
            f'File "{dsf.file_original_name}" moved to "{dsp.path_name}" in DS',
            caseid=case_identifier
        )
        return response_api_success(self._file_schema.dump(dsf))

    def delete_file(self, case_identifier, identifier):
        access_error = _check_case_access(case_identifier, _WRITE_LEVELS)
        if access_error:
            return access_error

        if not datastore_get_file(identifier, case_identifier):
            return response_api_not_found()

        has_error, logs = datastore_delete_file(identifier, case_identifier)
        if has_error:
            return response_api_error(logs)

        track_activity(f'File "{identifier}" deleted from DS', caseid=case_identifier)
        return response_api_deleted()

    # ---------------------------------------------------------------------
    # Folder CRUD
    # ---------------------------------------------------------------------
    def list_folders(self, case_identifier):
        access_error = _check_case_access(case_identifier, _READ_LEVELS)
        if access_error:
            return access_error

        folders = DataStorePath.query.filter(
            DataStorePath.path_case_id == case_identifier
        ).order_by(DataStorePath.path_id).all()
        return response_api_success(self._path_schema.dump(folders, many=True))

    def get_folder(self, case_identifier, identifier):
        access_error = _check_case_access(case_identifier, _READ_LEVELS)
        if access_error:
            return access_error

        dsp = datastore_get_path_node(identifier, case_identifier)
        if not dsp:
            return response_api_not_found()
        return response_api_success(self._path_schema.dump(dsp))

    def add_folder(self, case_identifier):
        access_error = _check_case_access(case_identifier, _WRITE_LEVELS)
        if access_error:
            return access_error

        data = request.get_json() or {}
        parent_node = data.get('parent_node')
        folder_name = data.get('folder_name')

        if not parent_node or not folder_name:
            return response_api_error('parent_node and folder_name are required')

        has_error, logs, node = datastore_add_child_node(parent_node, folder_name, case_identifier)
        if has_error:
            return response_api_error(logs)

        track_activity(f'Folder "{folder_name}" added to DS', caseid=case_identifier)
        return response_api_created(self._path_schema.dump(node))

    def rename_folder(self, case_identifier, identifier):
        access_error = _check_case_access(case_identifier, _WRITE_LEVELS)
        if access_error:
            return access_error

        dsp = datastore_get_path_node(identifier, case_identifier)
        if not dsp:
            return response_api_not_found()

        data = request.get_json() or {}
        folder_name = data.get('folder_name')
        if not folder_name:
            return response_api_error('folder_name is required')

        has_error, logs, dsp_base = datastore_rename_node(identifier, folder_name, case_identifier)
        if has_error:
            return response_api_error(logs)

        track_activity(
            f'Folder "{identifier}" renamed to "{folder_name}" in DS',
            caseid=case_identifier
        )
        return response_api_success(self._path_schema.dump(dsp_base))

    def move_folder(self, case_identifier, identifier):
        access_error = _check_case_access(case_identifier, _WRITE_LEVELS)
        if access_error:
            return access_error

        dsp = datastore_get_path_node(identifier, case_identifier)
        if not dsp:
            return response_api_not_found()

        data = request.get_json() or {}
        destination = data.get('destination_node')
        if destination is None:
            return response_api_error('Missing destination_node')

        dsp_dst = datastore_get_path_node(destination, case_identifier)
        if not dsp_dst:
            return response_api_error('Invalid destination node ID for this case')

        if dsp.path_id == dsp_dst.path_id:
            return response_api_error('Source and destination folders are the same')

        dsp.path_parent_id = dsp_dst.path_id
        db.session.commit()

        track_activity(
            f'Folder "{dsp.path_name}" moved to "{dsp_dst.path_name}"',
            caseid=case_identifier
        )
        return response_api_success(self._path_schema.dump(dsp))

    def delete_folder(self, case_identifier, identifier):
        access_error = _check_case_access(case_identifier, _WRITE_LEVELS)
        if access_error:
            return access_error

        dsp = datastore_get_path_node(identifier, case_identifier)
        if not dsp:
            return response_api_not_found()

        if dsp.path_is_root:
            return response_api_error('Cannot delete root folder')

        has_error, logs = datastore_delete_node(identifier, case_identifier)
        if has_error:
            return response_api_error(logs)

        track_activity(f'Folder "{identifier}" deleted from DS', caseid=case_identifier)
        return response_api_deleted()

    # ---------------------------------------------------------------------
    # Interactive (base64) upload used by the rich-text editor
    # ---------------------------------------------------------------------
    def add_interactive(self, case_identifier):
        access_error = _check_case_access(case_identifier, _WRITE_LEVELS)
        if access_error:
            return access_error

        dsp = datastore_get_interactive_path_node(case_identifier)
        if not dsp:
            return response_api_error('Invalid path node for this case')

        try:
            js_data = request.get_json() or {}

            try:
                file_content = base64.b64decode(js_data.get('file_content'))
                filename = js_data.get('file_original_name')
            except Exception as e:
                return response_api_error(str(e))

            if not filename:
                return response_api_error('Data error', data={'file_original_name': ['Missing filename']})

            dsf_sc, existed = self._file_schema.ds_store_file_b64(filename, file_content, dsp, case_identifier)

            track_activity(
                f'File "{dsf_sc.file_original_name}" added to DS',
                caseid=case_identifier
            )

            return response_api_created({
                'existed': existed,
                'file_url': f'/api/v2/cases/{case_identifier}/datastore/files/{dsf_sc.file_id}',
                **self._file_schema.dump(dsf_sc)
            })

        except marshmallow.exceptions.ValidationError as e:
            return response_api_error('Data error', data=e.messages)


datastore_operations = DatastoreOperations()
case_datastore_blueprint = Blueprint(
    'case_datastore_rest_v2',
    __name__,
    url_prefix='/<int:case_identifier>/datastore'
)


# Tree --------------------------------------------------------------------
@case_datastore_blueprint.get('/tree')
@ac_api_requires()
def datastore_tree(case_identifier):
    return datastore_operations.tree(case_identifier)


# Files -------------------------------------------------------------------
@case_datastore_blueprint.get('/files')
@ac_api_requires()
def datastore_list_files(case_identifier):
    return datastore_operations.list_files(case_identifier)


@case_datastore_blueprint.get('/files/<int:identifier>')
@ac_api_requires()
def datastore_view_file(case_identifier, identifier):
    # When a ?info=1 query parameter is set, return the file metadata as JSON
    # instead of streaming the file contents. Keeps a single URL for "the
    # file" while letting the UI fetch its info card separately.
    if _truthy(request.args.get('info')):
        return datastore_operations.get_file_info(case_identifier, identifier)
    return datastore_operations.view_file(case_identifier, identifier)


@case_datastore_blueprint.get('/files/<int:identifier>/info')
@ac_api_requires()
def datastore_file_info(case_identifier, identifier):
    return datastore_operations.get_file_info(case_identifier, identifier)


@case_datastore_blueprint.post('/folders/<int:folder_identifier>/files')
@ac_api_requires()
def datastore_add_file(case_identifier, folder_identifier):
    return datastore_operations.add_file(case_identifier, folder_identifier)


@case_datastore_blueprint.post('/files/<int:identifier>')
@ac_api_requires()
def datastore_update_file(case_identifier, identifier):
    return datastore_operations.update_file(case_identifier, identifier)


@case_datastore_blueprint.post('/files/<int:identifier>/move')
@ac_api_requires()
def datastore_move_file(case_identifier, identifier):
    return datastore_operations.move_file(case_identifier, identifier)


@case_datastore_blueprint.delete('/files/<int:identifier>')
@ac_api_requires()
def datastore_delete_file_route(case_identifier, identifier):
    return datastore_operations.delete_file(case_identifier, identifier)


@case_datastore_blueprint.post('/files/interactive')
@ac_api_requires()
def datastore_add_interactive_file(case_identifier):
    return datastore_operations.add_interactive(case_identifier)


# Folders -----------------------------------------------------------------
@case_datastore_blueprint.get('/folders')
@ac_api_requires()
def datastore_list_folders(case_identifier):
    return datastore_operations.list_folders(case_identifier)


@case_datastore_blueprint.post('/folders')
@ac_api_requires()
def datastore_add_folder(case_identifier):
    return datastore_operations.add_folder(case_identifier)


@case_datastore_blueprint.get('/folders/<int:identifier>')
@ac_api_requires()
def datastore_get_folder(case_identifier, identifier):
    return datastore_operations.get_folder(case_identifier, identifier)


@case_datastore_blueprint.post('/folders/<int:identifier>/rename')
@ac_api_requires()
def datastore_rename_folder(case_identifier, identifier):
    return datastore_operations.rename_folder(case_identifier, identifier)


@case_datastore_blueprint.post('/folders/<int:identifier>/move')
@ac_api_requires()
def datastore_move_folder(case_identifier, identifier):
    return datastore_operations.move_folder(case_identifier, identifier)


@case_datastore_blueprint.delete('/folders/<int:identifier>')
@ac_api_requires()
def datastore_delete_folder(case_identifier, identifier):
    return datastore_operations.delete_folder(case_identifier, identifier)
