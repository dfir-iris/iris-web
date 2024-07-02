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

import logging as log
# IMPORTS ------------------------------------------------
import os
import traceback
import urllib.parse

import marshmallow
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from flask_wtf import FlaskForm
from werkzeug import Response

import app
from app import db
from app.datamgmt.alerts.alerts_db import get_alert_status_by_name
from app.datamgmt.case.case_db import get_case, get_review_id_from_name
from app.datamgmt.case.case_db import register_case_protagonists
from app.datamgmt.case.case_db import save_case_tags
from app.datamgmt.client.client_db import get_client_list
from app.datamgmt.iris_engine.modules_db import get_pipelines_args_from_name
from app.datamgmt.iris_engine.modules_db import iris_module_exists
from app.datamgmt.manage.manage_assets_db import get_filtered_assets
from app.datamgmt.manage.manage_attribute_db import get_default_custom_attributes
from app.datamgmt.manage.manage_case_classifications_db import get_case_classifications_list
from app.datamgmt.manage.manage_case_state_db import get_case_states_list, get_case_state_by_name
from app.datamgmt.manage.manage_case_templates_db import get_case_templates_list, case_template_pre_modifier, \
    case_template_post_modifier
from app.datamgmt.manage.manage_cases_db import close_case, map_alert_resolution_to_case_status, get_filtered_cases
from app.datamgmt.manage.manage_cases_db import delete_case
from app.datamgmt.manage.manage_cases_db import get_case_details_rt
from app.datamgmt.manage.manage_cases_db import get_case_protagonists
from app.datamgmt.manage.manage_cases_db import list_cases_dict
from app.datamgmt.manage.manage_cases_db import reopen_case
from app.datamgmt.manage.manage_common import get_severities_list
from app.datamgmt.manage.manage_users_db import get_user_organisations
from app.forms import AddCaseForm
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access, \
    ac_current_user_has_permission
from app.iris_engine.access_control.utils import ac_fast_check_user_has_case_access
from app.iris_engine.access_control.utils import ac_set_new_case_access
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.module_handler.module_handler import configure_module_on_init
from app.iris_engine.module_handler.module_handler import instantiate_module_from_name
from app.iris_engine.tasker.tasks import task_case_update
from app.iris_engine.utils.common import build_upload_path
from app.iris_engine.utils.tracker import track_activity
from app.models.alerts import AlertStatus
from app.models.authorization import CaseAccessLevel
from app.models.authorization import Permissions
from app.models.models import Client, ReviewStatusList
from app.schema.marshables import CaseSchema, CaseDetailsSchema, CaseAssetsSchema
from app.util import ac_api_case_requires, add_obj_history_entry
from app.util import ac_api_requires
from app.util import ac_api_return_access_denied
from app.util import ac_case_requires
from app.util import ac_requires
from app.util import response_error
from app.util import response_success

manage_assets_blueprint = Blueprint('manage_assets',
                                    __name__,
                                    template_folder='templates')


@manage_assets_blueprint.route('/manage/assets/filter', methods=['GET'])
@ac_api_requires(no_cid_required=True)
def manage_assets_filter(caseid) -> Response:
    """ Returns a list of assets, filtered by the given parameters.
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    order_by = request.args.get('order_by', 'name', type=str)
    sort_dir = request.args.get('sort_dir', 'asc', type=str)

    case_id = request.args.get('case_id', None, type=int)
    client_id = request.args.get('customer_id', None, type=int)
    asset_type_id = request.args.get('asset_type_id', None, type=int)
    asset_id = request.args.get('asset_id', None, type=int)
    asset_name = request.args.get('asset_name', None, type=str)
    asset_description = request.args.get('asset_description', None, type=str)
    asset_ip = request.args.get('asset_ip', None, type=str)
    draw = request.args.get('draw', None, type=int)

    if type(draw) is not int:
        draw = 1

    if case_id and ac_fast_check_current_user_has_case_access(case_id, [CaseAccessLevel.deny_all]):
        return ac_api_return_access_denied()

    filtered_assets = get_filtered_assets(case_id=case_id,
                                          client_id=client_id,
                                          asset_type_id=asset_type_id,
                                          asset_id=asset_id,
                                          asset_name=asset_name,
                                          asset_description=asset_description,
                                          asset_ip=asset_ip,
                                          page=page,
                                          per_page=per_page,
                                          sort_by=order_by,
                                          sort_dir=sort_dir)

    assets = {
        'total': filtered_assets.total,
        'assets': CaseAssetsSchema().dump(filtered_assets.items, many=True),
        'last_page': filtered_assets.pages,
        'current_page': filtered_assets.page,
        'next_page': filtered_assets.next_num if filtered_assets.has_next else None,
        'draw': draw
    }

    return response_success('', data=assets)
