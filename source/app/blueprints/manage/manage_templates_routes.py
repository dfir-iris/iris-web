#!/usr/bin/env python3
#
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

# IMPORTS ------------------------------------------------
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

ALLOWED_EXTENSIONS = {'doc', 'docx'}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_random_string(length):
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str


# CONTENT ------------------------------------------------
@manage_templates_blueprint.route('/manage/templates')
@ac_requires(Permissions.server_administrator)
def manage_report_templates(caseid, url_redir):
    if url_redir:
        redirect(url_for('manage_templates.manage_report_templates', cid=caseid))

    form = AddReportTemplateForm()
    form.report_language.choices = [(c.id, c.name.capitalize()) for c in Languages.query.all()]

    # Return default page of case management
    return render_template('manage_templates.html', form=form)


@manage_templates_blueprint.route('/manage/templates/list')
@ac_api_requires(Permissions.server_administrator)
def report_templates_list(caseid):
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
        CaseTemplateReport.created_by_user,
        CaseTemplateReport.language,
        CaseTemplateReport.report_type
    ).all()

    data = [row._asdict() for row in templates]

    # Return the assets
    return response_success("", data=data)


@manage_templates_blueprint.route('/manage/templates/add', methods=['GET', 'POST'])
@ac_api_requires(Permissions.server_administrator)
def add_template(caseid):
    template = None
    form = AddReportTemplateForm()
    form.report_language.choices = [(c.id, c.name.capitalize()) for c in Languages.query.all()]
    form.report_type.choices = [(c.id, c.name) for c in ReportType.query.all()]

    report_template = CaseTemplateReport()
    if form.is_submitted():
        report_template.name = request.form.get('report_name', '', type=str)
        report_template.description = request.form.get('report_description', '', type=str)
        report_template.naming_format = request.form.get('report_name_format', '', type=str)
        report_template.language_id = request.form.get('report_language', '', type=int)
        report_template.report_type_id = request.form.get('report_type', '', type=int)

        report_template.created_by_user_id = current_user.id
        report_template.date_created = datetime.utcnow()

        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = get_random_string(18)

            try:

                file.save(os.path.join(app.config['TEMPLATES_PATH'], filename))

            except Exception as e:
                return response_error(f"Unable to add template {e}")

            report_template.internal_reference = filename

            db.session.add(report_template)
            db.session.commit()

            # Return the assets
            return response_success("Added successfully")

        else:
            return response_error("Unable to add a file")

    return render_template("modal_add_report_template.html", form=form, report_template=report_template)


@manage_templates_blueprint.route('/manage/templates/download/<report_id>', methods=['GET'])
@ac_api_requires(Permissions.server_administrator)
def download_template(report_id, caseid):
    if report_id != 0:
        report_template = CaseTemplateReport.query.filter(CaseTemplateReport.id == report_id).first()

        fpath = os.path.join(app.config['TEMPLATES_PATH'], report_template.internal_reference)

        resp = send_file(fpath, as_attachment=True, attachment_filename="{}.docx".format(report_template.name))

        return resp

    else:
        return response_error("Unable to download file")


@manage_templates_blueprint.route('/manage/templates/delete/<report_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def delete_template(report_id, caseid):
    error = ""

    report_template = CaseTemplateReport.query.filter(CaseTemplateReport.id == report_id).first()

    try:

        os.unlink(os.path.join(app.config['TEMPLATES_PATH'], report_template.internal_reference))

    except Exception as e:
        return response_error(f"Unable to delete {e}")

    CaseTemplateReport.query.filter(CaseTemplateReport.id == report_id).delete()

    db.session.commit()

    return response_success("Deleted successfully", data=error)
