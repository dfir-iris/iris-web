#!/usr/bin/env python3
#
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

from sqlalchemy import and_

from app.models import CaseAssets, AssetsType, EventCategory, CaseEventCategory, CasesEvent, CaseEventsAssets
from app import db


def get_case_events_graph(caseid):
    events = CaseEventsAssets.query.with_entities(
        CaseEventsAssets.event_id,
        CasesEvent.event_title,
        CaseAssets.asset_name,
        CaseAssets.asset_id,
        AssetsType.asset_name.label('asset_type'),
        CasesEvent.event_color,
        CaseAssets.asset_compromised,
        CaseAssets.asset_description,
        CaseAssets.asset_ip,
        CasesEvent.event_date,
        CasesEvent.event_tags
    ).filter(and_(
        CaseEventsAssets.case_id == caseid,
        CasesEvent.event_in_graph == True
    )).join(
        CaseEventsAssets.event,
        CaseEventsAssets.asset,
        CaseAssets.asset_type
    ).all()

    return events


def get_events_categories():
    return EventCategory.query.with_entities(
        EventCategory.id,
        EventCategory.name
    ).all()


def get_default_cat():
    cat = EventCategory.query.with_entities(
        EventCategory.id,
        EventCategory.name
    ).filter(
        EventCategory.name == "Unspecified"
    ).first()

    return [cat._asdict()]


def get_case_event(event_id, caseid):
    return CasesEvent.query.filter(
        CasesEvent.event_id == event_id,
        CasesEvent.case_id == caseid
    ).first()


def delete_event_category(event_id):
    CaseEventCategory.query.filter(
        CaseEventCategory.event_id == event_id
    ).delete()


def save_event_category(event_id, category_id):
    CaseEventCategory.query.filter(
        CaseEventCategory.event_id == event_id
    ).delete()

    cec = CaseEventCategory()
    cec.event_id = event_id
    cec.category_id = category_id

    db.session.add(cec)
    db.session.commit()


def update_event_assets(event_id, caseid, assets_list):
    if not assets_list:
        return False

    CaseEventsAssets.query.filter(
        CaseEventsAssets.event_id == event_id
    ).delete()

    for asset in assets_list:
        try:

            da = CaseEventsAssets.query.filter(
                CaseEventsAssets.event_id == event_id,
                CaseEventsAssets.asset_id == int(asset),
                CaseEventsAssets.case_id == caseid
            ).first()

            if not da:
                cea = CaseEventsAssets()
                cea.asset_id = int(asset)
                cea.event_id = event_id
                cea.case_id = caseid

                db.session.add(cea)
        except Exception as e:
            pass

    db.session.commit()
    return True


def get_case_assets(caseid):
    """
    Return a list of all assets linked to the current case
    :return: Tuple of assets
    """
    assets = [{'asset_name': '', 'asset_id': '0'}]

    assets_list = CaseAssets.query.with_entities(
        CaseAssets.asset_name,
        CaseAssets.asset_id,
        AssetsType.asset_name.label('type')
    ).filter(
        CaseAssets.case_id == caseid
    ).join(CaseAssets.asset_type).order_by(CaseAssets.asset_name).all()

    for asset in assets_list:
        assets.append({
            'asset_name': "{} ({})".format(asset.asset_name, asset.type),
            'asset_id': asset.asset_id
        })

    return assets