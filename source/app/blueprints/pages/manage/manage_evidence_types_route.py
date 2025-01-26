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

from app.datamgmt.manage.manage_evidence_types_db import get_evidence_type_by_id
from app.forms import EvidenceTypeForm
from app.models.authorization import Permissions
from app.blueprints.responses import response_error
from app.blueprints.access_controls import ac_requires

manage_evidence_types_blueprint = Blueprint('manage_evidence_types',
                                            __name__,
                                            template_folder='templates')


@manage_evidence_types_blueprint.route('/manage/evidence-types/update/<int:evidence_type_id>/modal',
                                       methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def update_evidence_type_modal(evidence_type_id: int, caseid: int, url_redir: bool) -> Union[str, Response]:
    """Update an evidence type

    Args:
        evidence_type_id (int): evidence type id
        caseid (int): case id
        url_redir (bool): redirect to url

    Returns:
        Flask Response object or str
    """
    if url_redir:
        return redirect(url_for('manage_evidence_types_blueprint.update_evidence_type_modal',
                                evidence_type_id=evidence_type_id, caseid=caseid))

    evidence_type_form = EvidenceTypeForm()
    evidence_type = get_evidence_type_by_id(evidence_type_id)
    if not evidence_type:
        return response_error(f"Invalid evidence type ID {evidence_type_id}")

    evidence_type_form.name.render_kw = {'value': evidence_type.name}
    evidence_type_form.description.render_kw = {'value': evidence_type.description}

    return render_template("modal_evidence_types.html", form=evidence_type_form,
                           evidence_type=evidence_type)


@manage_evidence_types_blueprint.route('/manage/evidence-types/add/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def add_evidence_type_modal(caseid: int, url_redir: bool) -> Union[str, Response]:
    """Add an evidence type

    Args:
        caseid (int): case id
        url_redir (bool): redirect to url

    Returns:
        Flask Response object or str
    """
    if url_redir:
        return redirect(url_for('manage_evidence_types_blueprint.add_evidence_type_modal',
                                caseid=caseid))

    evidence_form = EvidenceTypeForm()

    return render_template("modal_evidence_types.html", form=evidence_form, evidence_type=None)
