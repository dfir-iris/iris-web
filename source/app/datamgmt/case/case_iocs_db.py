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
from flask_login import current_user
from sqlalchemy import and_

from app import db
from app.datamgmt.states import update_ioc_state
from app.iris_engine.access_control.utils import ac_get_fast_user_cases_access
from app.models import CaseEventsIoc
from app.models import Cases
from app.models import Client
from app.models import Comments
from app.models import Ioc
from app.models import IocAssetLink
from app.models import IocComments
from app.models import IocLink
from app.models import IocType
from app.models import Tlp
from app.models.authorization import User


def get_iocs(caseid):
    iocs = IocLink.query.with_entities(
        Ioc.ioc_value,
        Ioc.ioc_id,
        Ioc.ioc_uuid
    ).filter(
        IocLink.case_id == caseid,
        IocLink.ioc_id == Ioc.ioc_id
    ).all()

    return iocs


def get_iocs_by_case(case_identifier) -> list[Ioc]:
    return Ioc.query.filter(
        IocLink.case_id == case_identifier,
        IocLink.ioc_id == Ioc.ioc_id
    ).all()


def get_ioc(ioc_id, caseid=None):
    if caseid:
        return IocLink.query.with_entities(
            Ioc
        ).filter(and_(
            Ioc.ioc_id == ioc_id,
            IocLink.case_id == caseid
        )).join(
            IocLink.ioc
        ).first()

    return Ioc.query.filter(Ioc.ioc_id == ioc_id).first()


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


def delete_ioc(ioc, caseid):
    with db.session.begin_nested():
        IocLink.query.filter(
            and_(
                IocLink.ioc_id == ioc.ioc_id,
                IocLink.case_id == caseid
            )
        ).delete()

        res = IocLink.query.filter(
                IocLink.ioc_id == ioc.ioc_id,
                ).all()

        if res:
            return False

        IocAssetLink.query.filter(
            IocAssetLink.ioc_id == ioc.ioc_id
        ).delete()

        CaseEventsIoc.query.filter(
            CaseEventsIoc.ioc_id == ioc.ioc_id
        ).delete()

        com_ids = IocComments.query.with_entities(
            IocComments.comment_id
        ).filter(
            IocComments.comment_ioc_id == ioc.ioc_id
        ).all()

        com_ids = [c.comment_id for c in com_ids]
        IocComments.query.filter(IocComments.comment_id.in_(com_ids)).delete()

        Comments.query.filter(Comments.comment_id.in_(com_ids)).delete()

        db.session.delete(ioc)

        update_ioc_state(caseid=caseid)

    return True


def get_detailed_iocs(caseid):
    detailed_iocs = (IocLink.query.with_entities(
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
    ).filter(
        and_(IocLink.case_id == caseid,
             IocLink.ioc_id == Ioc.ioc_id)
    ).join(IocLink.ioc)
     .join(Ioc.ioc_type)
     .join(Ioc.tlp)
     .order_by(IocType.type_name).all())

    return detailed_iocs


def get_ioc_links(ioc_id, caseid):
    search_condition = and_(Cases.case_id.in_([]))

    user_search_limitations = ac_get_fast_user_cases_access(current_user.id)
    if user_search_limitations:
        search_condition = and_(Cases.case_id.in_(user_search_limitations))

    ioc_link = (IocLink.query.with_entities(
        Cases.case_id,
        Cases.name.label('case_name'),
        Client.name.label('client_name')
    ).filter(and_(
        IocLink.ioc_id == ioc_id,
        IocLink.case_id != caseid,
        search_condition)
    ).join(IocLink.case)
     .join(Cases.client)
     .all())

    return ioc_link


def find_ioc(ioc_value, ioc_type_id):
    ioc = Ioc.query.filter(Ioc.ioc_value == ioc_value,
                           Ioc.ioc_type_id == ioc_type_id).first()

    return ioc


def add_ioc(ioc: Ioc, user_id, caseid):
    if not ioc:
        return None, False

    ioc.user_id = user_id

    db_ioc = find_ioc(ioc.ioc_value, ioc.ioc_type_id)

    if not db_ioc:
        db.session.add(ioc)

        update_ioc_state(caseid=caseid)
        db.session.commit()
        return ioc, False

    else:
        # IoC already exists
        return db_ioc, True


def find_ioc_link(ioc_id, caseid):
    db_link = IocLink.query.filter(
        IocLink.case_id == caseid,
        IocLink.ioc_id == ioc_id
    ).first()

    return db_link


def add_ioc_link(ioc_id, caseid):

    db_link = find_ioc_link(ioc_id, caseid)
    if db_link:
        # Link already exists
        return True
    else:
        link = IocLink()
        link.case_id = caseid
        link.ioc_id = ioc_id

        db.session.add(link)
        db.session.commit()

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
        return IocLink.query.with_entities(
            Ioc
        ).filter(and_(
            Ioc.ioc_value == ioc_value,
            IocLink.case_id == caseid
        )).join(
            IocLink.ioc
        ).first()

    return Ioc.query.filter(Ioc.ioc_value == ioc_value).first()
