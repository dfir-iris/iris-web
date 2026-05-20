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

import os
import random
import string
from datetime import datetime
from flask import Blueprint, url_for
from flask import flash
from flask import redirect
from flask import request
from flask import send_file
from werkzeug.utils import secure_filename

from app import app
from app.db import db
from app.blueprints.iris_user import iris_current_user
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.models.authorization import User
from app.models.models import CaseTemplateReport
from app.models.models import Languages
from app.models.models import ReportType
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success

_ALLOWED_EXTENSIONS = {'md', 'html', 'doc', 'docx'}

manage_templates_rest_blueprint = Blueprint('manage_templates_rest', __name__)


# TODO should move this function out in a module dedicated to random generation
def _get_random_string(length):
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str


@manage_templates_rest_blueprint.route('/manage/templates/list')
@ac_api_requires(Permissions.server_administrator)
def report_templates_list():
    # Get all templates
    templates = CaseTemplateReport.query.with_entities(
        CaseTemplateReport.name,
        CaseTemplateReport.description,
        CaseTemplateReport.naming_format,
        CaseTemplateReport.date_created,
        User.name.label('created_by'),
        Languages.code,
        ReportType.name.label('type_name'),
        CaseTemplateReport.id
    ).join(
        CaseTemplateReport.created_by_user
    ).join(
        CaseTemplateReport.language
    ).join(
        CaseTemplateReport.report_type
    ).all()

    data = [row._asdict() for row in templates]

    # Return the assets
    return response_success("", data=data)


def _allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in _ALLOWED_EXTENSIONS


@manage_templates_rest_blueprint.route('/manage/templates/add', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def add_template():

    report_template = CaseTemplateReport()

    report_template.name = request.form.get('report_name', '', type=str)
    report_template.description = request.form.get('report_description', '', type=str)
    report_template.naming_format = request.form.get('report_name_format', '', type=str)
    report_template.language_id = request.form.get('report_language', '', type=int)
    report_template.report_type_id = request.form.get('report_type', '', type=int)

    report_template.created_by_user_id = iris_current_user.id
    report_template.date_created = datetime.utcnow()

    template_file = request.files['file']
    if template_file.filename == '':
        flash('No selected file')
        return redirect(url_for('manage_templates.manage_templates'))

    if template_file and _allowed_file(template_file.filename):
        filename = secure_filename(template_file.filename)
        _, extension = os.path.splitext(filename)
        filename = _get_random_string(18) + extension

        try:

            template_file.save(os.path.join(app.config['TEMPLATES_PATH'], filename))

        except Exception as e:
            return response_error(f"Unable to add template. {e}")

        report_template.internal_reference = filename

        db.session.add(report_template)
        db.session.commit()

        track_activity(f"report template '{report_template.name}' added", ctx_less=True)

        ret = {
            "report_id": report_template.id,
            "report_name": report_template.name,
            "report_description": report_template.description,
            "report_language_id": report_template.language_id,
            "report_name_format": report_template.naming_format,
            "report_type_id": report_template.report_type_id
        }

        return response_success("Added successfully", data=ret)

    return response_error("File is invalid")


@manage_templates_rest_blueprint.route('/manage/templates/download/<report_id>', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def download_template(report_id):
    if report_id != 0:
        report_template = CaseTemplateReport.query.filter(CaseTemplateReport.id == report_id).first()

        fpath = os.path.join(app.config['TEMPLATES_PATH'], report_template.internal_reference)
        _, extension = os.path.splitext(report_template.internal_reference)
        resp = send_file(fpath, as_attachment=True, download_name=f"{report_template.name}.{extension}")

        return resp
    return response_error("Unable to download file")


@manage_templates_rest_blueprint.route('/manage/templates/delete/<report_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def delete_template(report_id):
    error = None

    report_template = CaseTemplateReport.query.filter(CaseTemplateReport.id == report_id).first()
    if report_template is None:
        return response_error('Template not found')

    report_name = report_template.name

    try:

        os.unlink(os.path.join(app.config['TEMPLATES_PATH'], report_template.internal_reference))

    except Exception as e:
        error = f"Template reference will be deleted but there has been some errors. {e}"

    finally:
        CaseTemplateReport.query.filter(CaseTemplateReport.id == report_id).delete()
        db.session.commit()

    if error:
        return response_error(error)

    track_activity(f"report template '{report_name}' deleted", ctx_less=True)
    return response_success("Deleted successfully", data=error)
