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

from app.datamgmt.db_operations import db_create
from app.datamgmt.db_operations import db_delete
from app.db import db
from app.datamgmt.states import update_timeline_state
from app.models.assets import AssetsType
from app.models.assets import CaseAssets
from app.models.models import CaseEventCategory
from app.models.models import CaseEventsAssets
from app.models.models import CaseEventsIoc
from app.models.cases import CasesEvent
from app.models.comments import Comments
from app.models.comments import EventComments
from app.models.models import EventCategory
from app.models.iocs import Ioc
from app.models.models import IocAssetLink
from app.models.models import IocType
from app.models.authorization import User


def get_case_events_assets_graph(caseid):
    events = CaseEventsAssets.query.with_entities(
        CaseEventsAssets.event_id,
        CasesEvent.event_uuid,
        CasesEvent.event_title,
        CaseAssets.asset_name,
        CaseAssets.asset_id,
        AssetsType.asset_name.label('type_name'),
        AssetsType.asset_icon_not_compromised,
        AssetsType.asset_icon_compromised,
        CasesEvent.event_color,
        CaseAssets.asset_compromise_status_id,
        CaseAssets.asset_description,
        CaseAssets.asset_ip,
        CasesEvent.event_date,
        CasesEvent.event_tags
    ).filter(and_(
        CaseEventsAssets.case_id == caseid,
        CasesEvent.event_in_graph == True
    )).join(
        CaseEventsAssets.event
    ).join(
        CaseEventsAssets.asset
    ).join(
        CaseAssets.asset_type
    ).all()

    return events


def get_case_events_ioc_graph(caseid):
    events = CaseEventsIoc.query.with_entities(
        CaseEventsIoc.event_id,
        CasesEvent.event_uuid,
        CasesEvent.event_title,
        CasesEvent.event_date,
        Ioc.ioc_id,
        Ioc.ioc_value,
        Ioc.ioc_description,
        IocType.type_name
    ).filter(and_(
        CaseEventsIoc.case_id == caseid,
        CasesEvent.event_in_graph == True
    )).join(
        CaseEventsIoc.event
    ).join(
        CaseEventsIoc.ioc
    ).join(
        Ioc.ioc_type
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


def get_case_event(event_id):
    return CasesEvent.query.filter(
        CasesEvent.event_id == event_id
    ).first()


def get_case_event_comments(event_id, caseid):
    return Comments.query.filter(
        EventComments.comment_event_id == event_id
    ).join(
        EventComments,
        Comments.comment_id == EventComments.comment_id
    ).order_by(
        Comments.comment_date.asc()
    ).all()


def get_case_events_comments_count(events_list):
    return EventComments.query.filter(
        EventComments.comment_event_id.in_(events_list)
    ).with_entities(
        EventComments.comment_event_id,
        EventComments.comment_id
    ).group_by(
        EventComments.comment_event_id,
        EventComments.comment_id
    ).all()


def get_case_event_comment(event_id, comment_id):
    return EventComments.query.filter(
        EventComments.comment_event_id == event_id,
        EventComments.comment_id == comment_id
    ).with_entities(
        Comments.comment_id,
        Comments.comment_text,
        Comments.comment_date,
        Comments.comment_update_date,
        Comments.comment_uuid,
        Comments.comment_user_id,
        Comments.comment_case_id,
        User.name,
        User.user
    ).join(
        EventComments.comment
    ).join(
        Comments.user
    ).first()


def delete_event_comment(user_identifier, event_id, comment_id):
    comment = Comments.query.filter(
        Comments.comment_id == comment_id,
        Comments.comment_user_id == user_identifier
    ).first()
    if not comment:
        return False, "You are not allowed to delete this comment"

    EventComments.query.filter(
        EventComments.comment_event_id == event_id,
        EventComments.comment_id == comment_id
    ).delete()

    db_delete(comment)

    return True, "Comment deleted"


def delete_events_comments_in_case(case_identifier):
    com_ids = EventComments.query.with_entities(
        EventComments.comment_id
    ).join(CasesEvent).filter(
        EventComments.comment_event_id == CasesEvent.event_id,
        CasesEvent.case_id == case_identifier
    ).all()

    com_ids = [c.comment_id for c in com_ids]
    EventComments.query.filter(EventComments.comment_id.in_(com_ids)).delete()
    Comments.query.filter(Comments.comment_id.in_(com_ids)).delete()


def add_comment_to_event(event_id, comment_id):
    ec = EventComments()
    ec.comment_event_id = event_id
    ec.comment_id = comment_id

    db_create(ec)


def delete_event_category(event_id):
    CaseEventCategory.query.filter(
        CaseEventCategory.event_id == event_id
    ).delete()


def get_event_category(event_id):
    cec = CaseEventCategory.query.filter(
        CaseEventCategory.event_id == event_id
    ).first()
    return cec


def save_event_category(event_id, category_id):
    CaseEventCategory.query.filter(
        CaseEventCategory.event_id == event_id
    ).delete()

    cec = CaseEventCategory()
    cec.event_id = event_id
    cec.category_id = category_id

    db_create(cec)


def get_event_assets_ids(event_id, caseid):
    assets_list = CaseEventsAssets.query.with_entities(
        CaseEventsAssets.asset_id
    ).filter(
        CaseEventsAssets.event_id == event_id,
        CaseEventsAssets.case_id == caseid
    ).all()

    return [x[0] for x in assets_list]


def get_event_iocs_ids(event_id, caseid):
    iocs_list = CaseEventsIoc.query.with_entities(
        CaseEventsIoc.ioc_id
    ).filter(
        CaseEventsIoc.event_id == event_id,
        CaseEventsIoc.case_id == caseid
    ).all()

    return [x[0] for x in iocs_list]


def update_event_assets(event_id, caseid, assets_list, iocs_list, sync_iocs_assets):

    CaseEventsAssets.query.filter(
        CaseEventsAssets.event_id == event_id,
        CaseEventsAssets.case_id == caseid
    ).delete()

    valid_assets = CaseAssets.query.with_entities(
        CaseAssets.asset_id
    ).filter(
        CaseAssets.asset_id.in_(assets_list),
        CaseAssets.case_id == caseid
    ).all()

    for asset in valid_assets:
        try:

            cea = CaseEventsAssets()
            cea.asset_id = int(asset.asset_id)
            cea.event_id = event_id
            cea.case_id = caseid

            db.session.add(cea)

            if sync_iocs_assets:
                for ioc in iocs_list:
                    link = IocAssetLink.query.filter(
                        IocAssetLink.asset_id == int(asset.asset_id),
                        IocAssetLink.ioc_id == int(ioc)
                    ).first()

                    if link is None:

                        ial = IocAssetLink()
                        ial.asset_id = int(asset.asset_id)
                        ial.ioc_id = int(ioc)

                        db.session.add(ial)

        except Exception as e:
            return False, str(e)

    db.session.commit()
    return True, ''


def update_event_iocs(event_id, caseid, iocs_list):

    CaseEventsIoc.query.filter(
        CaseEventsIoc.event_id == event_id,
        CaseEventsIoc.case_id == caseid
    ).delete()

    valid_iocs = Ioc.query.filter(
        Ioc.ioc_id.in_(iocs_list),
        Ioc.case_id == caseid
    ).all()

    for ioc in valid_iocs:
        try:

            cea = CaseEventsIoc()
            cea.ioc_id = int(ioc.ioc_id)
            cea.event_id = event_id
            cea.case_id = caseid

            db.session.add(cea)

        except Exception as e:
            return False, str(e)

    db.session.commit()
    return True, ''


def get_case_assets_for_tm(caseid):
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
            'asset_name': f'{asset.asset_name} ({asset.type})',
            'asset_id': asset.asset_id
        })

    return assets


def get_case_iocs_for_tm(caseid):
    iocs = [{'ioc_value': '', 'ioc_id': '0'}]

    iocs_list = Ioc.query.with_entities(
        Ioc.ioc_value,
        Ioc.ioc_id
    ).filter(
        Ioc.case_id == caseid
    ).order_by(
        Ioc.ioc_value
    ).all()

    for ioc in iocs_list:
        iocs.append({
            'ioc_value': f'{ioc.ioc_value}',
            'ioc_id': ioc.ioc_id
        })

    return iocs


def delete_event(user_identifier, event):
    case_identifier = event.case_id
    delete_event_category(event.event_id)

    CaseEventsAssets.query.filter(
        CaseEventsAssets.event_id == event.event_id,
        CaseEventsAssets.case_id == case_identifier
    ).delete()

    CaseEventsIoc.query.filter(
        CaseEventsIoc.event_id == event.event_id,
        CaseEventsIoc.case_id == case_identifier
    ).delete()

    com_ids = EventComments.query.with_entities(
        EventComments.comment_id
    ).filter(
        EventComments.comment_event_id == event.event_id
    ).all()

    com_ids = [c.comment_id for c in com_ids]
    EventComments.query.filter(EventComments.comment_id.in_(com_ids)).delete()

    Comments.query.filter(Comments.comment_id.in_(com_ids)).delete()

    db.session.commit()

    db.session.delete(event)
    update_timeline_state(case_identifier, user_identifier)

    db.session.commit()


def get_category_by_name(cat_name):
    return EventCategory.query.filter(
        EventCategory.name == cat_name,
    ).first()


def get_default_category():
    return EventCategory.query.with_entities(
        EventCategory.id,
        EventCategory.name
    ).filter(
        EventCategory.name == "Unspecified"
    ).first()


def get_events_by_case(case_identifier):
    return CasesEvent.query.filter(and_(
        CasesEvent.case_id == case_identifier,
        CasesEvent.event_in_summary
    )).order_by(
        CasesEvent.event_date
    ).all()
