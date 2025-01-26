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

from typing import Union

from flask import Blueprint
from flask import Response
from flask import url_for
from flask import render_template
from werkzeug.utils import redirect

from app.datamgmt.manage.manage_case_classifications_db import get_case_classification_by_id
from app.forms import CaseClassificationForm
from app.models.authorization import Permissions
from app.blueprints.responses import response_error
from app.blueprints.access_controls import ac_requires

manage_case_classification_blueprint = Blueprint('manage_case_classifications',
                                                 __name__,
                                                 template_folder='templates')


@manage_case_classification_blueprint.route('/manage/case-classifications/update/<int:classification_id>/modal',
                                            methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def update_case_classification_modal(classification_id: int, caseid: int, url_redir: bool) -> Union[str, Response]:
    """Update a case classification

    Args:
        classification_id (int): case classification id
        caseid (int): case id
        url_redir (bool): redirect to url

    Returns:
        Flask Response object or str
    """
    if url_redir:
        return redirect(url_for('manage_case_classification_blueprint.update_case_classification_modal',
                                classification_id=classification_id, caseid=caseid))

    classification_form = CaseClassificationForm()
    case_classification = get_case_classification_by_id(classification_id)
    if not case_classification:
        return response_error(f"Invalid case classification ID {classification_id}")

    classification_form.name.render_kw = {'value': case_classification.name}
    classification_form.name_expanded.render_kw = {'value': case_classification.name_expanded}
    classification_form.description.render_kw = {'value': case_classification.description}

    return render_template("modal_case_classification.html", form=classification_form,
                           case_classification=case_classification)


@manage_case_classification_blueprint.route('/manage/case-classifications/add/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def add_case_classification_modal(caseid: int, url_redir: bool) -> Union[str, Response]:
    """Add a case classification

    Args:
        caseid (int): case id
        url_redir (bool): redirect to url

    Returns:
        Flask Response object or str
    """
    if url_redir:
        return redirect(url_for('manage_case_classification_blueprint.add_case_classification_modal',
                                caseid=caseid))

    classification_form = CaseClassificationForm()

    return render_template("modal_case_classification.html", form=classification_form, case_classification=None)
