from sqlalchemy import and_
from functools import reduce

from app.logger import logger
from app.blueprints.iris_user import iris_current_user
from app.datamgmt.manage.manage_cases_db import user_list_cases_view
from app.datamgmt.conversions import convert_sort_direction
from app.models.cases import Cases
from app.models.assets import CaseAssets
from app.models.customers import Client


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

    conditions.append(CaseAssets.case_id.in_(user_list_cases_view(iris_current_user.id)))

    data = CaseAssets.query.filter(*conditions)

    # If client ID then we need to join the client table
    if client_id:
        data = data.join(CaseAssets.case).join(Cases.client)

    if sort_by is not None:
        order_func = convert_sort_direction(sort_dir)

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
        logger.exception(f"Failed to get filtered assets: {e}")
        raise e

    return filtered_assets
