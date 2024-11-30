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

import datetime

from flask_login import current_user
from sqlalchemy import and_
from sqlalchemy import func

from app import db, app
from app.datamgmt.states import update_assets_state
from app.models import AnalysisStatus, CaseStatus
from app.models import AssetComments
from app.models import AssetsType
from app.models import CaseAssets
from app.models import CaseEventsAssets
from app.models import Cases
from app.models import Comments
from app.models import CompromiseStatus
from app.models import Ioc
from app.models import IocAssetLink
from app.models import IocLink
from app.models import IocType
from app.models.authorization import User


log = app.logger

def create_asset(asset, caseid, user_id):

    asset.date_added = datetime.datetime.utcnow()
    asset.date_update = datetime.datetime.utcnow()
    asset.case_id = caseid
    asset.user_id = user_id

    db.session.add(asset)
    update_assets_state(caseid=caseid, userid=user_id)

    db.session.commit()

    return asset


def get_assets(caseid):
    assets = CaseAssets.query.with_entities(
        CaseAssets.asset_id,
        CaseAssets.asset_uuid,
        CaseAssets.asset_name,
        AssetsType.asset_name.label('asset_type'),
        AssetsType.asset_icon_compromised,
        AssetsType.asset_icon_not_compromised,
        CaseAssets.asset_description,
        CaseAssets.asset_domain,
        CaseAssets.asset_compromise_status_id,
        CaseAssets.asset_ip,
        CaseAssets.asset_type_id,
        AnalysisStatus.name.label('analysis_status'),
        CaseAssets.analysis_status_id,
        CaseAssets.asset_tags
    ).filter(
        CaseAssets.case_id == caseid,
    ).join(
        CaseAssets.asset_type
    ).join(
        CaseAssets.analysis_status
    ).all()

    return assets


def get_raw_assets(caseid):
    assets = CaseAssets.query.filter(
        CaseAssets.case_id == caseid
    ).all()

    return assets


def get_assets_name(caseid):
    assets_names = CaseAssets.query.with_entities(
        CaseAssets.asset_name
    ).filter(
        CaseAssets.case_id == caseid
    ).all()

    return assets_names


def get_asset(asset_id, caseid):
    asset = CaseAssets.query.filter(
        CaseAssets.asset_id == asset_id,
        CaseAssets.case_id == caseid
    ).first()

    return asset


def update_asset(asset_name, asset_description, asset_ip, asset_info, asset_domain,
                 asset_compromise_status_id, asset_type, asset_id, caseid, analysis_status, asset_tags):
    asset = get_asset(asset_id, caseid)
    asset.asset_name = asset_name
    asset.asset_description = asset_description
    asset.asset_ip = asset_ip
    asset.asset_info = asset_info
    asset.asset_domain = asset_domain
    asset.asset_compromise_status_id = asset_compromise_status_id
    asset.asset_type_id = asset_type
    asset.analysis_status_id = analysis_status
    asset.asset_tags = asset_tags

    update_assets_state(caseid=caseid)

    db.session.commit()


def delete_asset(asset_id, caseid):
    case_asset = get_asset(asset_id, caseid)
    if case_asset is None:
        return

    if case_asset.case_id and case_asset.alerts is not None:

        CaseEventsAssets.query.filter(
            case_asset.asset_id == CaseEventsAssets.asset_id
        ).delete()

        case_asset.case_id = None
        db.session.commit()
        return

    with db.session.begin_nested():
        delete_ioc_asset_link(asset_id)

        # Delete the relevant records from the CaseEventsAssets table
        CaseEventsAssets.query.filter(
            CaseEventsAssets.case_id == caseid,
            CaseEventsAssets.asset_id == asset_id
        ).delete()

        # Delete the relevant records from the AssetComments table
        com_ids = AssetComments.query.with_entities(
            AssetComments.comment_id
        ).filter(
            AssetComments.comment_asset_id == asset_id,
        ).all()

        com_ids = [c.comment_id for c in com_ids]
        AssetComments.query.filter(AssetComments.comment_id.in_(com_ids)).delete()

        Comments.query.filter(
            Comments.comment_id.in_(com_ids)
        ).delete()

        # Directly delete the relevant records from the CaseAssets table
        CaseAssets.query.filter(
            CaseAssets.asset_id == asset_id,
            CaseAssets.case_id == caseid
        ).delete()

        update_assets_state(caseid=caseid)


def get_assets_types():
    assets_types = [(c.asset_id, c.asset_name) for c
                    in AssetsType.query.with_entities(AssetsType.asset_name,
                                                      AssetsType.asset_id).order_by(AssetsType.asset_name)
                    ]

    return assets_types


def get_unspecified_analysis_status_id():
    """
    Get the id of the 'Unspecified' analysis status
    """
    analysis_status = AnalysisStatus.query.filter(
        AnalysisStatus.name == 'Unspecified'
    ).first()

    return analysis_status.id if analysis_status else None


def get_analysis_status_list():
    analysis_status = [(c.id, c.name) for c in AnalysisStatus.query.with_entities(
        AnalysisStatus.id,
        AnalysisStatus.name
    )]

    return analysis_status


def get_compromise_status_list():
    return [(e.value, e.name.replace('_', ' ').capitalize()) for e in CompromiseStatus]


def get_compromise_status_dict():
    return [{'value': e.value, 'name': e.name.replace('_', ' ').capitalize()} for e in CompromiseStatus]


def get_case_outcome_status_dict():
    return [{'value': e.value, 'name': e.name.replace('_', ' ').capitalize()} for e in CaseStatus]


def get_asset_type_id(asset_type_name):
    assets_type_id = AssetsType.query.with_entities(
        AssetsType.asset_id
    ).filter(
        func.lower(AssetsType.asset_name) == asset_type_name
    ).first()

    return assets_type_id


def get_assets_ioc_links(caseid):

    ioc_links_req = IocAssetLink.query.with_entities(
        Ioc.ioc_id,
        Ioc.ioc_value,
        IocAssetLink.asset_id
    ).filter(
        Ioc.ioc_id == IocAssetLink.ioc_id,
        IocLink.case_id == caseid,
        IocLink.ioc_id == Ioc.ioc_id
    ).all()

    return ioc_links_req

def get_similar_assets(asset_name, asset_type_id, caseid, customer_id, cases_limitation):

    linked_assets = CaseAssets.query.with_entities(
        Cases.name.label('case_name'),
        Cases.open_date.label('case_open_date'),
        CaseAssets.asset_description,
        CaseAssets.asset_compromise_status_id,
        CaseAssets.asset_id,
        CaseAssets.case_id
    ).filter(
        Cases.client_id == customer_id,
        CaseAssets.case_id != caseid
    ).filter(
        CaseAssets.asset_name == asset_name,
        CaseAssets.asset_type_id == asset_type_id,
        Cases.case_id.in_(cases_limitation)
    ).join(CaseAssets.case).all()

    return (lasset._asdict() for lasset in linked_assets)


def delete_ioc_asset_link(asset_id):
    IocAssetLink.query.filter(
        IocAssetLink.asset_id == asset_id
    ).delete()


def get_linked_iocs_from_asset(asset_id):
    iocs = IocAssetLink.query.with_entities(
        Ioc.ioc_id,
        Ioc.ioc_value
    ).filter(
        IocAssetLink.asset_id == asset_id,
        Ioc.ioc_id == IocAssetLink.ioc_id
    ).all()

    return iocs


def set_ioc_links(ioc_list, asset_id):
    if ioc_list is None:
        return False, "Empty IOC list"

    # Reset IOC list
    delete_ioc_asset_link(asset_id)

    for ioc in ioc_list:
        ial = IocAssetLink()
        ial.asset_id = asset_id
        ial.ioc_id = ioc

        db.session.add(ial)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.exception(e)
        return True, e.__str__()

    return False, ""


def get_linked_iocs_id_from_asset(asset_id):
    iocs = IocAssetLink.query.with_entities(
        IocAssetLink.ioc_id
    ).filter(
        IocAssetLink.asset_id == asset_id
    ).all()

    return iocs


def get_linked_iocs_finfo_from_asset(asset_id):
    iocs = IocAssetLink.query.with_entities(
        Ioc.ioc_id,
        Ioc.ioc_value,
        Ioc.ioc_tags,
        Ioc.ioc_type_id,
        IocType.type_name,
        Ioc.ioc_description,
        Ioc.ioc_tlp_id
    ).filter(and_(
        IocAssetLink.asset_id == asset_id,
        IocAssetLink.ioc_id == Ioc.ioc_id
    )).join(Ioc.ioc_type).all()

    return iocs


def get_case_asset_comments(asset_id):
    return Comments.query.filter(
        AssetComments.comment_asset_id == asset_id
    ).with_entities(
        Comments
    ).join(AssetComments,
           Comments.comment_id == AssetComments.comment_id
    ).order_by(
        Comments.comment_date.asc()
    ).all()


def add_comment_to_asset(asset_id, comment_id):
    ec = AssetComments()
    ec.comment_asset_id = asset_id
    ec.comment_id = comment_id

    db.session.add(ec)
    db.session.commit()


def get_case_assets_comments_count(asset_id):
    return AssetComments.query.filter(
        AssetComments.comment_asset_id.in_(asset_id)
    ).with_entities(
        AssetComments.comment_asset_id,
        AssetComments.comment_id
    ).group_by(
        AssetComments.comment_asset_id,
        AssetComments.comment_id
    ).all()


def get_case_asset_comment(asset_id, comment_id):
    return AssetComments.query.filter(
        AssetComments.comment_asset_id == asset_id,
        AssetComments.comment_id == comment_id
    ).with_entities(
        Comments.comment_id,
        Comments.comment_text,
        Comments.comment_date,
        Comments.comment_update_date,
        Comments.comment_uuid,
        User.name,
        User.user
    ).join(
        AssetComments.comment
    ).join(
        Comments.user
    ).first()


def delete_asset_comment(asset_id, comment_id, case_id):
    comment = Comments.query.filter(
        Comments.comment_id == comment_id,
        Comments.comment_user_id == current_user.id
    ).first()
    if not comment:
        return False, "You are not allowed to delete this comment"

    AssetComments.query.filter(
        AssetComments.comment_asset_id == asset_id,
        AssetComments.comment_id == comment_id
    ).delete()

    db.session.delete(comment)
    db.session.commit()

    return True, "Comment deleted"

def get_asset_by_name(asset_name, caseid):
    asset = CaseAssets.query.filter(
        CaseAssets.asset_name == asset_name,
        CaseAssets.case_id == caseid
    ).first()
    return asset
