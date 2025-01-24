#  IRIS Source Code
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
from flask import redirect
from flask import render_template
from flask import url_for

from app.datamgmt.manage.manage_case_templates_db import get_case_template_by_id
from app.forms import CaseTemplateForm
from app.forms import AddAssetForm
from app.models.models import CaseTemplate
from app.models.authorization import Permissions
from app.blueprints.access_controls import ac_requires
from app.blueprints.responses import response_error

manage_case_templates_blueprint = Blueprint('manage_case_templates',
                                            __name__,
                                            template_folder='templates')


@manage_case_templates_blueprint.route('/manage/case-templates', methods=['GET'])
@ac_requires(Permissions.case_templates_read)
def manage_case_templates(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_case_templates.manage_case_templates', cid=caseid))

    form = AddAssetForm()

    return render_template('manage_case_templates.html', form=form)


@manage_case_templates_blueprint.route('/manage/case-templates/<int:cur_id>/modal', methods=['GET'])
@ac_requires(Permissions.case_templates_read)
def case_template_modal(cur_id, caseid, url_redir):
    """Get a case template

    Args:
        cur_id (int): case template id

    Returns:
        HTML Template: Case template modal
    """
    if url_redir:
        return redirect(url_for('manage_case_templates.manage_case_templates', cid=caseid))

    form = CaseTemplateForm()

    case_template = get_case_template_by_id(cur_id)
    if not case_template:
        return response_error(f"Invalid Case template ID {cur_id}")

    # Temporary : for now we build the full JSON form object based on case templates attributes
    # Next step : add more fields to the form
    case_template_dict = {
        "name": case_template.name,
        "display_name": case_template.display_name,
        "description": case_template.description,
        "author": case_template.author,
        "title_prefix": case_template.title_prefix,
        "summary": case_template.summary,
        "tags": case_template.tags,
        "tasks": case_template.tasks,
        "note_directories": case_template.note_directories,
        "classification": case_template.classification
    }

    form.case_template_json.data = case_template_dict

    return render_template("modal_case_template.html", form=form, case_template=case_template)


@manage_case_templates_blueprint.route('/manage/case-templates/add/modal', methods=['GET'])
@ac_requires(Permissions.case_templates_write, no_cid_required=True)
def add_template_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_case_templates.manage_case_templates', cid=caseid))

    case_template = CaseTemplate()
    form = CaseTemplateForm()
    form.case_template_json.data = {
        "name": "Template name",
        "display_name": "Template Display Name",
        "description": "Template description",
        "author": "YOUR NAME",
        "classification": "known-template-classification",
        "title_prefix": "[PREFIX]",
        "summary": "Summary to be set",
        "tags": ["ransomware", "malware"],
        "tasks": [
            {
                "title": "Task 1",
                "description": "Task 1 description",
                "tags": ["tag1", "tag2"]
            }
        ],
        "note_directories": [
            {
                "title": "Note group 1",
                "notes": [
                    {
                        "title": "Note 1",
                        "content": "Note 1 content"
                    }
                ]
            }
        ]
    }

    return render_template("modal_case_template.html", form=form, case_template=case_template)


@manage_case_templates_blueprint.route('/manage/case-templates/upload/modal', methods=['GET'])
@ac_requires(Permissions.case_templates_write, no_cid_required=True)
def upload_template_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_case_templates.manage_case_templates', cid=caseid))

    return render_template("modal_upload_case_template.html")
