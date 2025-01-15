#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

from flask_login import current_user
from sqlalchemy import and_
from sqlalchemy import desc
from sqlalchemy import asc
from functools import reduce

import app
from app.datamgmt.manage.manage_cases_db import user_list_cases_view
from app.models.models import CaseAssets
from app.models.models import Client
from app.models.cases import Cases


def get_filtered_assets(case_id=None,
                        client_id=None,
                        asset_type_id=None,
                        asset_id=None,
                        asset_name=None,
                        asset_description=None,
                        asset_ip=None,
                        page=1,
                        per_page=10,
                        sort_by='name',
                        sort_dir='asc'):
    """ Returns a list of assets, filtered by the given parameters.
    """

    conditions = []
    if case_id:
        conditions.append(CaseAssets.case_id == case_id)

    if client_id:
        conditions.append(Client.client_id == client_id)

    if asset_type_id:
        conditions.append(CaseAssets.asset_type_id == asset_type_id)

    if asset_id:
        conditions.append(CaseAssets.asset_id == asset_id)

    if asset_name:
        conditions.append(CaseAssets.asset_name.ilike(f'%{asset_name}%'))

    if asset_description:
        conditions.append(CaseAssets.asset_description.ilike(f'%{asset_description}%'))

    if asset_ip:
        conditions.append(CaseAssets.asset_ip.ilike(f'%{asset_ip}%'))

    if len(conditions) > 1:
        conditions = [reduce(and_, conditions)]

    conditions.append(CaseAssets.case_id.in_(user_list_cases_view(current_user.id)))

    data = CaseAssets.query.filter(*conditions)

    # If client ID then we need to join the client table
    if client_id:
        data = data.join(CaseAssets.case).join(Cases.client)

    if sort_by is not None:
        order_func = desc if sort_dir == 'desc' else asc

        if sort_by == 'name':
            data = data.order_by(order_func(CaseAssets.asset_name))
        elif sort_by == 'description':
            data = data.order_by(order_func(CaseAssets.asset_description))
        elif sort_by == 'ip':
            data = data.order_by(order_func(CaseAssets.asset_ip))
        elif sort_by == 'type':
            data = data.order_by(order_func(CaseAssets.asset_type_id))
        elif sort_by == 'id':
            data = data.order_by(order_func(CaseAssets.asset_id))
        elif sort_by == 'client':
            data = data.order_by(order_func(Client.name))
        elif sort_by == 'case':
            data = data.order_by(order_func(CaseAssets.case_id))
        else:
            data = data.order_by(order_func(CaseAssets.asset_name))

    try:

        filtered_assets = data.paginate(page=page, per_page=per_page)

    except Exception as e:
        app.logger.exception(f"Failed to get filtered assets: {e}")
        raise e

    return filtered_assets
