#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS) - DFIR-IRIS Team
#  ir@cyberactionlab.net - contact@dfir-iris.org
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

from app.business.iocs import iocs_get
from app.models.errors import ObjectNotFoundError
from app.datamgmt.case.assets_type import get_assets_types
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_iocs_db import get_case_iocs_comments_count
from app.datamgmt.case.case_iocs_db import get_ioc_types_list
from app.datamgmt.case.case_iocs_db import get_tlps
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.forms import ModalAddCaseAssetForm
from app.forms import ModalAddCaseIOCForm
from app.models.authorization import CaseAccessLevel
from app.models.iocs import Ioc
from app.blueprints.access_controls import ac_case_requires
from app.blueprints.responses import response_error

case_ioc_blueprint = Blueprint(
    'case_ioc',
    __name__,
    template_folder='templates'
)


@case_ioc_blueprint.route('/case/ioc', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_ioc(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_ioc.case_ioc', cid=caseid, redirect=True))

    form = ModalAddCaseAssetForm()
    form.asset_id.choices = get_assets_types()

    # Retrieve the assets linked to the investigation
    case = get_case(caseid)

    return render_template("case_ioc.html", case=case, form=form)


@case_ioc_blueprint.route('/case/ioc/add/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.full_access)
def case_add_ioc_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_assets.case_assets', cid=caseid, redirect=True))

    form = ModalAddCaseIOCForm()
    form.ioc_type_id.choices = [(row['type_id'], row['type_name']) for row in get_ioc_types_list()]
    form.ioc_tlp_id.choices = get_tlps()

    attributes = get_default_custom_attributes('ioc')

    return render_template("modal_add_case_ioc.html", form=form, ioc=Ioc(), attributes=attributes)


@case_ioc_blueprint.route('/case/ioc/<int:cur_id>/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_view_ioc_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_assets.case_assets', cid=caseid, redirect=True))

    form = ModalAddCaseIOCForm()
    try:
        ioc = iocs_get(cur_id)

        form.ioc_type_id.choices = [(row['type_id'], row['type_name']) for row in get_ioc_types_list()]
        form.ioc_tlp_id.choices = get_tlps()

        # Render the IOC
        form.ioc_tags.render_kw = {'value': ioc.ioc_tags}
        form.ioc_description.data = ioc.ioc_description
        form.ioc_value.data = ioc.ioc_value
        comments_map = get_case_iocs_comments_count([cur_id])

        return render_template('modal_add_case_ioc.html', form=form, ioc=ioc, attributes=ioc.custom_attributes,
                               comments_map=comments_map)

    except ObjectNotFoundError:
        return response_error('Invalid IOC ID for this case')


@case_ioc_blueprint.route('/case/ioc/<int:cur_id>/comments/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_ioc_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_ioc.case_ioc', cid=caseid, redirect=True))

    try:
        ioc = iocs_get(cur_id)

        return render_template('modal_conversation.html', element_id=cur_id, element_type='ioc', title=ioc.ioc_value)
    except ObjectNotFoundError:
        return response_error('Invalid ioc ID')
