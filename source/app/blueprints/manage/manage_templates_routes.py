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

import os
import random
import string
from datetime import datetime
from flask import Blueprint
from flask import flash
from flask import redirect
from flask import render_template
from flask import request
from flask import send_file
from flask import url_for
from flask_login import current_user

from app import app
from app import db
from app.forms import AddReportTemplateForm
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.models.authorization import User
from app.models.models import CaseTemplateReport
from app.models.models import Languages
from app.models.models import ReportType
from app.util import ac_api_requires
from app.util import ac_requires
from app.util import response_error
from app.util import response_success

manage_templates_blueprint = Blueprint(
    'manage_templates',
    __name__,
    template_folder='templates'
)

ALLOWED_EXTENSIONS = {'md', 'html', 'doc', 'docx'}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_random_string(length):
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str


# CONTENT ------------------------------------------------
@manage_templates_blueprint.route('/manage/templates')
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_report_templates(caseid, url_redir):
    if url_redir:
        redirect(url_for('manage_templates.manage_report_templates', cid=caseid))

    form = AddReportTemplateForm()
    form.report_language.choices = [(c.id, c.name.capitalize()) for c in Languages.query.all()]

    # Return default page of case management
    return render_template('manage_templates.html', form=form)


@manage_templates_blueprint.route('/manage/templates/list')
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


@manage_templates_blueprint.route('/manage/templates/add/modal', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def add_template_modal():
    report_template = CaseTemplateReport()
    form = AddReportTemplateForm()
    form.report_language.choices = [(c.id, c.name.capitalize()) for c in Languages.query.all()]
    form.report_type.choices = [(c.id, c.name) for c in ReportType.query.all()]

    return render_template("modal_add_report_template.html", form=form, report_template=report_template)


@manage_templates_blueprint.route('/manage/templates/add', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def add_template():

    report_template = CaseTemplateReport()

    report_template.name = request.form.get('report_name', '', type=str)
    report_template.description = request.form.get('report_description', '', type=str)
    report_template.naming_format = request.form.get('report_name_format', '', type=str)
    report_template.language_id = request.form.get('report_language', '', type=int)
    report_template.report_type_id = request.form.get('report_type', '', type=int)

    report_template.created_by_user_id = current_user.id
    report_template.date_created = datetime.utcnow()

    template_file = request.files['file']
    if template_file.filename == '':
        flash('No selected file')
        return redirect(request.url)

    if template_file and allowed_file(template_file.filename):
        _, extension = os.path.splitext(template_file.filename)
        filename = get_random_string(18) + extension

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


@manage_templates_blueprint.route('/manage/templates/download/<report_id>', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def download_template(report_id):
    if report_id != 0:
        report_template = CaseTemplateReport.query.filter(CaseTemplateReport.id == report_id).first()

        fpath = os.path.join(app.config['TEMPLATES_PATH'], report_template.internal_reference)
        _, extension = os.path.splitext(report_template.internal_reference)
        resp = send_file(fpath, as_attachment=True, download_name=f"{report_template.name}.{extension}")

        return resp

    else:
        return response_error("Unable to download file")


@manage_templates_blueprint.route('/manage/templates/delete/<report_id>', methods=['POST'])
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
