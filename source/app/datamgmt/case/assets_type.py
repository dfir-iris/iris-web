#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
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

from sqlalchemy import func

from app.models.assets import AssetsType


def get_assets_types():
    assets_types = [(c.asset_id, c.asset_name) for c
                    in AssetsType.query.with_entities(AssetsType.asset_name,
                                                      AssetsType.asset_id).order_by(AssetsType.asset_name)
                    ]

    return assets_types


def get_asset_type_by_name_case_insensitive(asset_type_name) -> AssetsType:
    asset_type_name = asset_type_name.lower()
    return AssetsType.query.with_entities(
        AssetsType.asset_id
    ).filter(
        func.lower(AssetsType.asset_name) == asset_type_name
    ).first()


def exists_asset_type_with_name(session, asset_name) -> bool:
    instance = session.query(AssetsType).filter_by(asset_name=asset_name).first()
    return instance is not None


def add_asset_type(session, asset_type):
    session.add(asset_type)
    session.commit()
