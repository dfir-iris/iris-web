#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
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

from app.models import AnalysisStatus, IocType, AssetsType, EventCategory


def search_analysis_status_by_name(name: str, exact_match: bool = False) -> AnalysisStatus:
    """
    Search an analysis status by its name

    args:
        name: the name of the analysis status
        exact_match: if True, the name must be exactly the same as the one in the database

    return: the analysis status
    """
    if exact_match:
        return AnalysisStatus.query.filter(func.lower(AnalysisStatus.name) == name.lower()).all()

    return AnalysisStatus.query.filter(AnalysisStatus.name.ilike(f'%{name}%')).all()


def search_ioc_type_by_name(name: str, exact_match: bool = False) -> IocType:
    """
    Search an IOC type by its name

    args:
        name: the name of the IOC type
        exact_match: if True, the name must be exactly the same as the one in the database

    return: the IOC type
    """
    if exact_match:
        return IocType.query.filter(func.lower(IocType.type_name) == name.lower()).all()

    return IocType.query.filter(IocType.type_name.ilike(f'%{name}%')).all()


def search_asset_type_by_name(name: str, exact_match: bool = False) -> AssetsType:
    """
    Search an asset type by its name

    args:
        name: the name of the asset type
        exact_match: if True, the name must be exactly the same as the one in the database

    return: the asset type
    """
    if exact_match:
        return AssetsType.query.filter(func.lower(AssetsType.asset_name) == name.lower()).all()

    return AssetsType.query.filter(AssetsType.asset_name.ilike(f'%{name}%')).all()


def search_event_category_by_name(name: str, exact_match: bool = False) -> AssetsType:
    """
    Search an event category by its name

    args:
        name: the name of the event category
        exact_match: if True, the name must be exactly the same as the one in the database

    return: the event category
    """
    if exact_match:
        return EventCategory.query.filter(func.lower(EventCategory.name) == name.lower()).all()

    return EventCategory.query.filter(EventCategory.name.ilike(f'%{name}%')).all()
