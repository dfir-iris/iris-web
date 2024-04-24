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
from flask import request
from werkzeug import Response

from app.datamgmt.manage.manage_assets_db import get_filtered_assets
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import CaseAssetsSchema
from app.util import ac_api_requires
from app.util import ac_api_return_access_denied
from app.util import response_success

manage_assets_blueprint = Blueprint('manage_assets',
                                    __name__,
                                    template_folder='templates')


@manage_assets_blueprint.route('/manage/assets/filter', methods=['GET'])
@ac_api_requires()
def manage_assets_filter() -> Response:
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
