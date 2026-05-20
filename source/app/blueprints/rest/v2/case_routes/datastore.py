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
import marshmallow.exceptions
from flask import Blueprint
from flask import request
from flask import send_file
from pathlib import Path

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.business.cases import cases_exists
from app.datamgmt.datastore.datastore_db import datastore_get_file
from app.datamgmt.datastore.datastore_db import datastore_get_interactive_path_node
from app.datamgmt.datastore.datastore_db import datastore_get_local_file_path
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import DSFileSchema


class DatastoreOperations:
    """Case-scoped datastore file operations used by the rich-text editor
    (inline image uploads embedded in notes and case summaries).

    Only the two endpoints the editor actually needs are exposed here:
    the interactive upload and the file view. The broader tree / folder
    management still lives on the legacy `datastore_rest_blueprint` until
    that UI is migrated too.
    """

    @staticmethod
    def _check_case_access(case_identifier, access_levels):
        if not cases_exists(case_identifier):
            return response_api_not_found()

        if not ac_fast_check_current_user_has_case_access(case_identifier, access_levels):
            return ac_api_return_access_denied(caseid=case_identifier)

        return None

    def add_interactive(self, case_identifier):
        access_error = self._check_case_access(case_identifier, [CaseAccessLevel.full_access])
        if access_error:
            return access_error

        dsp = datastore_get_interactive_path_node(case_identifier)
        if not dsp:
            return response_api_error('Invalid path node for this case')

        dsf_schema = DSFileSchema()
        try:
            js_data = request.get_json() or {}

            try:
                file_content = base64.b64decode(js_data.get('file_content'))
                filename = js_data.get('file_original_name')
            except Exception as e:
                return response_api_error(str(e))

            if not filename:
                return response_api_error('Data error', data={'file_original_name': ['Missing filename']})

            dsf_sc, existed = dsf_schema.ds_store_file_b64(filename, file_content, dsp, case_identifier)

            track_activity(
                f'File "{dsf_sc.file_original_name}" added to DS',
                caseid=case_identifier
            )

            # URL is returned relative to /api/v2 so the frontend can embed it
            # directly as an <img src>. It's a REST path the browser can GET
            # without any further rewriting — `cid` is part of the path.
            return response_api_created({
                'existed': existed,
                'file_url': f'/api/v2/cases/{case_identifier}/datastore/files/{dsf_sc.file_id}',
                **dsf_schema.dump(dsf_sc)
            })

        except marshmallow.exceptions.ValidationError as e:
            return response_api_error('Data error', data=e.messages)

    def view(self, case_identifier, identifier):
        access_error = self._check_case_access(
            case_identifier,
            [CaseAccessLevel.read_only, CaseAccessLevel.full_access]
        )
        if access_error:
            return access_error

        # Sanity-check that the file actually belongs to this case before
        # resolving its on-disk location. `datastore_get_local_file_path`
        # already filters by case id, but this keeps 404s consistent with
        # the rest of the v2 case routes.
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

        resp = send_file(dsf.file_local_name, as_attachment=False, download_name=destination_name)

        track_activity(
            f'File "{destination_name}" downloaded',
            caseid=case_identifier,
            display_in_ui=False
        )
        return resp


datastore_operations = DatastoreOperations()
case_datastore_blueprint = Blueprint(
    'case_datastore_rest_v2',
    __name__,
    url_prefix='/<int:case_identifier>/datastore'
)


@case_datastore_blueprint.post('/files/interactive')
@ac_api_requires()
def datastore_add_interactive_file(case_identifier):
    return datastore_operations.add_interactive(case_identifier)


@case_datastore_blueprint.get('/files/<int:identifier>')
@ac_api_requires()
def datastore_view_file(case_identifier, identifier):
    return datastore_operations.view(case_identifier, identifier)
