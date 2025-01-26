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

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import url_for

from app.forms import AddReportTemplateForm
from app.models.authorization import Permissions
from app.models.models import CaseTemplateReport
from app.models.models import Languages
from app.models.models import ReportType
from app.blueprints.access_controls import ac_requires

manage_templates_blueprint = Blueprint(
    'manage_templates',
    __name__,
    template_folder='templates'
)


@manage_templates_blueprint.route('/manage/templates')
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_report_templates(caseid, url_redir):
    if url_redir:
        redirect(url_for('manage_templates.manage_report_templates', cid=caseid))

    form = AddReportTemplateForm()
    form.report_language.choices = [(c.id, c.name.capitalize()) for c in Languages.query.all()]

    # Return default page of case management
    return render_template('manage_templates.html', form=form)


@manage_templates_blueprint.route('/manage/templates/add/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def add_template_modal(caseid, url_redir):
    if url_redir:
        redirect(url_for('manage_templates.manage_report_templates', cid=caseid))

    report_template = CaseTemplateReport()
    form = AddReportTemplateForm()
    form.report_language.choices = [(c.id, c.name.capitalize()) for c in Languages.query.all()]
    form.report_type.choices = [(c.id, c.name) for c in ReportType.query.all()]

    return render_template("modal_add_report_template.html", form=form, report_template=report_template)
