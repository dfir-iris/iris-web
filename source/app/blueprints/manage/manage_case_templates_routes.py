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

# IMPORTS ------------------------------------------------
import json
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from marshmallow import ValidationError

from app import db
from app.datamgmt.manage.manage_case_templates_db import get_case_templates_list
from app.datamgmt.manage.manage_case_templates_db import get_case_template_by_id
from app.datamgmt.manage.manage_case_templates_db import validate_case_template
from app.datamgmt.manage.manage_case_templates_db import delete_case_template_by_id
from app.forms import CaseTemplateForm, AddAssetForm
from app.models import CaseTemplate
from app.models.authorization import Permissions
from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import CaseTemplateSchema
from app.util import ac_api_requires
from app.util import ac_requires_case_identifier
from app.util import ac_requires
from app.util import response_error
from app.util import response_success

manage_case_templates_blueprint = Blueprint('manage_case_templates',
                                            __name__,
                                            template_folder='templates')


# CONTENT ------------------------------------------------
@manage_case_templates_blueprint.route('/manage/case-templates', methods=['GET'])
@ac_requires(Permissions.case_templates_read)
def manage_case_templates(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_case_templates.manage_case_templates', cid=caseid))

    form = AddAssetForm()

    return render_template('manage_case_templates.html', form=form)


@manage_case_templates_blueprint.route('/manage/case-templates/list', methods=['GET'])
@ac_api_requires()
def list_case_templates():
    """Show a list of case templates

    Returns:
        Response: List of case templates
    """
    case_templates = get_case_templates_list()

    # Return the attributes
    return response_success("", data=case_templates)


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
@ac_api_requires(Permissions.case_templates_write)
def add_template_modal():
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
        "tags": ["ransomware","malware"],
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
@ac_api_requires(Permissions.case_templates_write)
def upload_template_modal():
    return render_template("modal_upload_case_template.html")


@manage_case_templates_blueprint.route('/manage/case-templates/add', methods=['POST'])
@ac_api_requires(Permissions.case_templates_write)
@ac_requires_case_identifier()
def add_case_template(caseid):
    data = request.get_json()
    if not data:
        return response_error("Invalid request")

    case_template_json = data.get('case_template_json')
    if not case_template_json:
        return response_error("Invalid request")

    try:
        case_template_dict = json.loads(case_template_json)
    except Exception as e:
        return response_error("Invalid JSON", data=str(e))

    try:
        logs = validate_case_template(case_template_dict, update=False)
        if logs is not None:
            return response_error("Found errors in case template", data=logs)
    except Exception as e:
        return response_error("Found errors in case template", data=str(e))

    try:
        case_template_dict["created_by_user_id"] = current_user.id
        case_template_data = CaseTemplateSchema().load(case_template_dict)
        case_template = CaseTemplate(**case_template_data)
        db.session.add(case_template)
        db.session.commit()
    except Exception as e:
        return response_error("Could not add case template into DB", data=str(e))

    track_activity(f"Case template '{case_template.name}' added", caseid=caseid, ctx_less=True)

    return response_success("Added successfully", data=CaseTemplateSchema().dump(case_template))


@manage_case_templates_blueprint.route('/manage/case-templates/update/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.case_templates_write)
def update_case_template(cur_id):
    if not request.is_json:
        return response_error("Invalid request")

    case_template = get_case_template_by_id(cur_id)
    if not case_template:
        return response_error(f"Invalid Case template ID {cur_id}")

    data = request.get_json()
    updated_case_template_json = data.get('case_template_json')
    if not updated_case_template_json:
        return response_error("Invalid request")

    try:
        updated_case_template_dict = json.loads(updated_case_template_json)
    except Exception as e:
        return response_error("Invalid JSON", data=str(e))

    try:
        logs = validate_case_template(updated_case_template_dict, update=True)
        if logs is not None:
            return response_error("Found errors in case template", data=logs)
    except Exception as e:
        return response_error("Found errors in case template", data=str(e))

    case_template_schema = CaseTemplateSchema()

    try:
        # validate the request data and load it into an instance of the `CaseTemplate` object
        case_template_data = case_template_schema.load(updated_case_template_dict, partial=True)
        # update the existing `case_template` object with the new data
        case_template.update_from_dict(case_template_data)
        # commit the changes to the database
        db.session.commit()
    except ValidationError as error:
        return response_error("Could not validate case template", data=str(error))

    return response_success("Case template updated")


@manage_case_templates_blueprint.route('/manage/case-templates/delete/<int:case_template_id>', methods=['POST'])
@ac_api_requires(Permissions.case_templates_write)
@ac_requires_case_identifier()
def delete_case_template(case_template_id, caseid):
    case_template = get_case_template_by_id(case_template_id)
    if case_template is None:
        return response_error('Case template not found')

    case_template_name = case_template.name

    delete_case_template_by_id(case_template_id)
    db.session.commit()

    track_activity(f"Case template '{case_template_name}' deleted", caseid=caseid, ctx_less=True)
    return response_success("Deleted successfully")
