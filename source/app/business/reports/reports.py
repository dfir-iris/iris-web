#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
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
import os

from app.models.errors import ObjectNotFoundError, BusinessProcessingError
from app.business.reports.reporter import IrisMakeMdReport, IrisMakeDocReport
from app.datamgmt.case.case_db import get_case
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.models import CaseTemplateReport


def generate_investigation_report(caseid, report_id, safe_mode, tmp_dir):
    call_modules_hook('on_preload_report_create', report_id, caseid=caseid)
    report = CaseTemplateReport.query.filter(CaseTemplateReport.id == report_id).first()
    if not report:
        raise ObjectNotFoundError()
    _, report_format = os.path.splitext(report.internal_reference)
    if report_format in ('.md', '.html'):
        mreport = IrisMakeMdReport(tmp_dir, report_id, caseid, safe_mode)
        fpath = mreport.generate_md_report('Investigation')

    elif report_format == '.docx':
        mreport = IrisMakeDocReport(tmp_dir, report_id, caseid, safe_mode)
        fpath = mreport.generate_doc_report('Investigation')

    else:
        raise BusinessProcessingError('Report error', data='Unknown report format.')

    with open(fpath, 'rb') as rfile:
        encoded_file = base64.b64encode(rfile.read()).decode('utf-8')
    res = get_case(caseid)
    data = {
        'report_id': report_id,
        'file_path': fpath,
        'case_id': res.case_id,
        'user_name': res.user.name,
        'file': encoded_file
    }
    call_modules_hook('on_postload_report_create', data, caseid=caseid)
    track_activity('generated a report')
    return fpath


def generate_activities_report(caseid, report_id, safe_mode, tmp_dir):
    call_modules_hook('on_preload_activities_report_create', report_id, caseid=caseid)
    report = CaseTemplateReport.query.filter(CaseTemplateReport.id == report_id).first()
    if not report:
        raise ObjectNotFoundError()
    # Get file extension
    _, report_format = os.path.splitext(report.internal_reference)
    # Depending on the template format, the generation process is different
    if report_format == '.docx':
        mreport = IrisMakeDocReport(tmp_dir, report_id, caseid, safe_mode)
        fpath = mreport.generate_doc_report('Activities')

    elif report_format in ('.md', '.html'):
        mreport = IrisMakeMdReport(tmp_dir, report_id, caseid, safe_mode)
        fpath = mreport.generate_md_report('Activities')

    else:
        raise BusinessProcessingError('Report error', data='Unknown report format.')
    call_modules_hook('on_postload_activities_report_create', report_id, caseid=caseid)
    track_activity('generated a report')
    return fpath
