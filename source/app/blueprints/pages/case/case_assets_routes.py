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

from app.datamgmt.case.case_assets_db import get_analysis_status_list
from app.datamgmt.case.case_assets_db import get_asset
from app.datamgmt.case.case_assets_db import get_assets_types
from app.datamgmt.case.case_assets_db import get_case_assets_comments_count
from app.datamgmt.case.case_assets_db import get_compromise_status_list
from app.datamgmt.case.case_assets_db import get_linked_iocs_id_from_asset
from app.datamgmt.case.case_db import get_case
from app.datamgmt.case.case_iocs_db import get_iocs
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.forms import AssetBasicForm
from app.forms import ModalAddCaseAssetForm
from app.models.authorization import CaseAccessLevel
from app.blueprints.access_controls import ac_case_requires
from app.blueprints.responses import response_error

case_assets_blueprint = Blueprint('case_assets',
                                  __name__,
                                  template_folder='templates')


@case_assets_blueprint.route('/case/assets', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_assets(caseid, url_redir):
    """
    Returns the page of case assets, with the list of available assets types.
    :return: The HTML page of case assets
    """
    if url_redir:
        return redirect(url_for('case_assets.case_assets', cid=caseid, redirect=True))

    form = ModalAddCaseAssetForm()
    # Get asset types from database
    form.asset_id.choices = get_assets_types()

    # Retrieve the assets linked to the investigation
    case = get_case(caseid)

    return render_template("case_assets.html", case=case, form=form)


@case_assets_blueprint.route('/case/assets/add/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.full_access)
def add_asset_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_assets.case_assets', cid=caseid, redirect=True))

    form = AssetBasicForm()

    form.asset_type_id.choices = get_assets_types()
    form.analysis_status_id.choices = get_analysis_status_list()
    form.asset_compromise_status_id.choices = get_compromise_status_list()

    # Get IoCs from the case
    ioc = get_iocs(caseid)
    attributes = get_default_custom_attributes('asset')

    return render_template("modal_add_case_multi_asset.html", form=form, asset=None, ioc=ioc, attributes=attributes)


@case_assets_blueprint.route('/case/assets/<int:cur_id>/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def asset_view_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_assets.case_assets', cid=caseid, redirect=True))

    # Get IoCs from the case
    case_iocs = get_iocs(caseid)

    # Get IoCs already linked to the asset
    asset_iocs = get_linked_iocs_id_from_asset(cur_id)

    ioc_prefill = [row for row in asset_iocs]

    # Build the form
    form = AssetBasicForm()
    asset = get_asset(cur_id)

    form.asset_name.render_kw = {'value': asset.asset_name}
    form.asset_description.data = asset.asset_description
    form.asset_info.data = asset.asset_info
    form.asset_ip.render_kw = {'value': asset.asset_ip}
    form.asset_domain.render_kw = {'value': asset.asset_domain}
    form.asset_compromise_status_id.choices = get_compromise_status_list()
    form.asset_type_id.choices = get_assets_types()
    form.analysis_status_id.choices = get_analysis_status_list()
    form.asset_tags.render_kw = {'value': asset.asset_tags}
    comments_map = get_case_assets_comments_count([cur_id])

    return render_template("modal_add_case_asset.html", form=form, asset=asset, map={}, ioc=case_iocs,
                           ioc_prefill=ioc_prefill, attributes=asset.custom_attributes, comments_map=comments_map)


@case_assets_blueprint.route('/case/assets/<int:cur_id>/comments/modal', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_comment_asset_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_task.case_task', cid=caseid, redirect=True))

    asset = get_asset(cur_id)
    if not asset:
        return response_error('Invalid asset ID')

    return render_template("modal_conversation.html", element_id=cur_id, element_type='assets',
                           title=asset.asset_name)
