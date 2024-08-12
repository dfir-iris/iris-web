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

import logging

from functools import reduce

from flask_login import current_user
from sqlalchemy import and_, desc, asc

from app import db, app
from app.datamgmt.states import update_ioc_state
from app.iris_engine.access_control.utils import ac_get_fast_user_cases_access
from app.models import Cases
from app.models import Client
from app.models import Comments
from app.models import Ioc
from app.models import IocAssetLink
from app.models import IocComments
from app.models import IocType
from app.models import Tlp
from app.models.authorization import User, UserCaseEffectiveAccess, CaseAccessLevel


def get_iocs(caseid):
    iocs = Ioc.query.filter(Ioc.case_id == caseid).all()

    return iocs


def get_iocs_by_case(case_identifier) -> list[Ioc]:
    return Ioc.query.filter(
        Ioc.case_id == case_identifier,
    ).all()


def get_ioc(ioc_id, caseid=None):
    q = Ioc.query.filter(Ioc.ioc_id == ioc_id)

    if caseid:
        q = q.filter(Ioc.case_id == caseid)

    return q.first()


def update_ioc(ioc_type, ioc_tags, ioc_value, ioc_description, ioc_tlp, userid, ioc_id):
    ioc = get_ioc(ioc_id)

    if ioc:
        ioc.ioc_type = ioc_type
        ioc.ioc_tags = ioc_tags
        ioc.ioc_value = ioc_value
        ioc.ioc_description = ioc_description
        ioc.ioc_tlp_id = ioc_tlp
        ioc.user_id = userid

        db.session.commit()

    else:
        return False


def delete_ioc(ioc: Ioc, caseid):
    db.session.delete(ioc)

    update_ioc_state(caseid=ioc.case_id)

    return True


def get_detailed_iocs(caseid):
    detailed_iocs = (Ioc.query.with_entities(
        Ioc.ioc_id,
        Ioc.ioc_uuid,
        Ioc.ioc_value,
        Ioc.ioc_type_id,
        IocType.type_name.label('ioc_type'),
        Ioc.ioc_type_id,
        Ioc.ioc_description,
        Ioc.ioc_tags,
        Ioc.ioc_misp,
        Tlp.tlp_name,
        Tlp.tlp_bscolor,
        Ioc.ioc_tlp_id
    ).filter(Ioc.case_id == caseid)
     .join(Ioc.ioc_type)
     .join(Ioc.tlp)
     .order_by(IocType.type_name).all())

    return detailed_iocs


def get_ioc_links(ioc_id, caseid):
    search_condition = and_(Cases.case_id.in_([]))

    user_search_limitations = ac_get_fast_user_cases_access(current_user.id)
    if user_search_limitations:
        search_condition = and_(Cases.case_id.in_(user_search_limitations))

    ioc = Ioc.query.filter(Ioc.ioc_id == ioc_id).first()

    # Search related iocs based on value and type
    related_iocs = (Ioc.query.with_entities(
        Cases.case_id,
        Cases.name.label('case_name'),
        Client.name.label('client_name')
    ).filter(and_(
        Ioc.ioc_value == ioc.ioc_value,
        Ioc.ioc_type_id == ioc.ioc_type_id,
        Ioc.ioc_id != ioc_id,
        search_condition)
    ).join(Ioc.case)
     .join(Cases.client)
     .all())

    return related_iocs


def find_ioc(ioc_value, ioc_type_id):
    ioc = Ioc.query.filter(Ioc.ioc_value == ioc_value,
                           Ioc.ioc_type_id == ioc_type_id).first()

    return ioc


def add_ioc(ioc: Ioc, user_id, caseid):
    if not ioc:
        return None, False

    ioc.user_id = user_id
    ioc.case_id = caseid
    db.session.add(ioc)

    update_ioc_state(caseid=caseid)
    db.session.commit()
    return ioc, False


def find_ioc_link(ioc_id, caseid):
    logging.warning("Method 'find_ioc_link' is deprecated. It is no longer possible to link IOCs with cases.")


def add_ioc_link(ioc_id, caseid):
    logging.warning("Method 'add_ioc_link' is deprecated. It is no longer possible to link IOCs with cases.")

    return False


def get_ioc_types_list():
    ioc_types = IocType.query.with_entities(
        IocType.type_id,
        IocType.type_name,
        IocType.type_description,
        IocType.type_taxonomy,
        IocType.type_validation_regex,
        IocType.type_validation_expect,
    ).all()

    l_types = [row._asdict() for row in ioc_types]
    return l_types


def add_ioc_type(name:str, description:str, taxonomy:str):
    ioct = IocType(type_name=name,
                   type_description=description,
                   type_taxonomy=taxonomy
                )

    db.session.add(ioct)
    db.session.commit()
    return ioct


def check_ioc_type_id(type_id: int):
    type_id = IocType.query.filter(
        IocType.type_id == type_id
    ).first()

    return type_id


def get_ioc_type_id(type_name: str):
    type_id = IocType.query.filter(
        IocType.type_name == type_name
    ).first()

    return type_id if type_id else None


def get_tlps():
    return [(tlp.tlp_id, tlp.tlp_name) for tlp in Tlp.query.all()]


def get_tlps_dict():
    tlpDict = {}
    for tlp in Tlp.query.all():
        tlpDict[tlp.tlp_name]=tlp.tlp_id 
    return tlpDict


def get_case_ioc_comments(ioc_id):
    return Comments.query.filter(
        IocComments.comment_ioc_id == ioc_id
    ).with_entities(
        Comments
    ).join(
        IocComments,
        Comments.comment_id == IocComments.comment_id
    ).order_by(
        Comments.comment_date.asc()
    ).all()


def add_comment_to_ioc(ioc_id, comment_id):
    ec = IocComments()
    ec.comment_ioc_id = ioc_id
    ec.comment_id = comment_id

    db.session.add(ec)
    db.session.commit()


def get_case_iocs_comments_count(iocs_list):
    return IocComments.query.filter(
        IocComments.comment_ioc_id.in_(iocs_list)
    ).with_entities(
        IocComments.comment_ioc_id,
        IocComments.comment_id
    ).group_by(
        IocComments.comment_ioc_id,
        IocComments.comment_id
    ).all()


def get_case_ioc_comment(ioc_id, comment_id):
    return (IocComments.query.filter(
        IocComments.comment_ioc_id == ioc_id,
        IocComments.comment_id == comment_id
    ).with_entities(
        Comments.comment_id,
        Comments.comment_text,
        Comments.comment_date,
        Comments.comment_update_date,
        Comments.comment_uuid,
        User.name,
        User.user
    ).join(IocComments.comment)
            .join(Comments.user).first())


def delete_ioc_comment(ioc_id, comment_id):
    comment = Comments.query.filter(
        Comments.comment_id == comment_id,
        Comments.comment_user_id == current_user.id
    ).first()
    if not comment:
        return False, "You are not allowed to delete this comment"

    IocComments.query.filter(
        IocComments.comment_ioc_id == ioc_id,
        IocComments.comment_id == comment_id
    ).delete()

    db.session.delete(comment)
    db.session.commit()

    return True, "Comment deleted"


def get_ioc_by_value(ioc_value, caseid=None):
    if caseid:
        Ioc.query.filter(Ioc.ioc_value == ioc_value, Ioc.case_id == caseid).first()

    return Ioc.query.filter(Ioc.ioc_value == ioc_value).first()


def user_list_cases_view(user_id):
    res = UserCaseEffectiveAccess.query.with_entities(
        UserCaseEffectiveAccess.case_id
    ).filter(and_(
        UserCaseEffectiveAccess.user_id == user_id,
        UserCaseEffectiveAccess.access_level != CaseAccessLevel.deny_all.value
    )).all()

    return [r.case_id for r in res]


def build_filter_ioc_query(
        caseid: int = None,
        ioc_type_id: int = None,
        ioc_type: str = None,
        ioc_tlp_id: int = None,
        ioc_value: str = None,
        ioc_description: str = None,
        ioc_tags: str = None,
        sort_by=None,
        sort_dir='asc'):
    """
    Get a list of iocs from the database, filtered by the given parameters
    """

    conditions = []
    if ioc_type_id is not None:
        conditions.append(Ioc.ioc_type_id == ioc_type_id)

    if ioc_type is not None:
        conditions.append(Ioc.ioc_type == ioc_type)

    if ioc_tlp_id is not None:
        conditions.append(Ioc.ioc_tlp_id == ioc_tlp_id)

    if ioc_value is not None:
        conditions.append(Ioc.ioc_value == ioc_value)

    if ioc_description is not None:
        conditions.append(Ioc.ioc_description == ioc_description)

    if ioc_tags is not None:
        conditions.append(Ioc.ioc_tags == ioc_tags)

    if caseid is not None:
        conditions.append(Ioc.case_id == caseid)

    query = Ioc.query.filter(*conditions)

    if sort_by is not None:
        order_func = desc if sort_dir == "desc" else asc

        if sort_by == 'opened_by':
            query = query.join(User, Ioc.user_id == User.id).order_by(order_func(User.name))

        elif hasattr(Ioc, sort_by):
            query = query.order_by(order_func(getattr(Ioc, sort_by)))

    return query


def get_filtered_iocs(
        caseid: int = None,
        ioc_type_id: int = None,
        ioc_type: str = None,
        ioc_tlp_id: int = None,
        ioc_value: str = None,
        ioc_description: str = None,
        ioc_tags: str = None,
        per_page: int = None,
        page: int = None,
        sort_by=None,
        sort_dir='asc'
        ):

    data = build_filter_ioc_query(caseid=caseid, ioc_type_id=ioc_type_id, ioc_type=ioc_type, ioc_tlp_id=ioc_tlp_id, ioc_value=ioc_value,
                                  ioc_description=ioc_description, ioc_tags=ioc_tags,
                                  sort_by=sort_by, sort_dir=sort_dir)

    try:
        filtered_iocs = data.paginate(page=page, per_page=per_page, error_out=False)

    except Exception as e:
        app.logger.exception(f"Error getting cases: {str(e)}")
        return None

    return filtered_iocs
