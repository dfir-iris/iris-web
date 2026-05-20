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

import tempfile

from flask import Blueprint
from flask import request
from flask import send_file

from app.models.errors import ObjectNotFoundError
from app.models.errors import BusinessProcessingError
from app.business.reports.reports import generate_investigation_report, generate_activities_report

from app.models.authorization import CaseAccessLevel

from app.util import FileRemover
from app.blueprints.access_controls import ac_requires_case_identifier
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.responses import response_error

reports_rest_blueprint = Blueprint('reports_rest', __name__)

file_remover = FileRemover()


@reports_rest_blueprint.route('/case/report/generate-activities/<int:report_id>', methods=['GET'])
@ac_api_requires()
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def download_case_activity(report_id, caseid):
    if not report_id:
        return response_error('Unknown report', status=404)
    safe_mode = False
    if request.args.get('safe-mode') == 'true':
        safe_mode = True

    tmp_dir = tempfile.mkdtemp()

    try:
        fpath = generate_activities_report(caseid, report_id, safe_mode, tmp_dir)

    except ObjectNotFoundError:
        return response_error('Unknown report', status=404)

    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())

    resp = send_file(fpath, as_attachment=True)
    file_remover.cleanup_once_done(resp, tmp_dir)

    return resp


@reports_rest_blueprint.route('/case/report/generate-investigation/<int:report_id>', methods=['GET'])
@ac_api_requires()
@ac_requires_case_identifier(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def generate_report(report_id, caseid):
    if not report_id:
        return response_error('Unknown report', status=404)
    safe_mode = False
    if request.args.get('safe-mode') == 'true':
        safe_mode = True

    tmp_dir = tempfile.mkdtemp()

    try:
        fpath = generate_investigation_report(caseid, report_id, safe_mode, tmp_dir)

    except ObjectNotFoundError:
        return response_error('Unknown report', status=404)

    except BusinessProcessingError as e:
        return response_error(e.get_message(), data=e.get_data())

    resp = send_file(fpath, as_attachment=True)
    file_remover.cleanup_once_done(resp, tmp_dir)

    return resp
