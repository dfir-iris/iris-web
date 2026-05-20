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
from app.datamgmt.filtering import get_filtered_data
from app.datamgmt.states import update_ioc_state
from app.models.alerts import Alert
from app.models.cases import Cases
from app.models.cases import CasesEvent
from app.models.customers import Client
from app.models.assets import CaseAssets
from app.models.comments import Comments
from app.models.comments import IocComments
from app.models.iocs import Ioc
from app.models.models import IocType
from app.models.iocs import Tlp
from app.models.authorization import User
from app.models.pagination_parameters import PaginationParameters
from app.util import add_obj_history_entry


relationship_model_map = {
    'case': Cases,
    'assets': CaseAssets,
    'tlp': Tlp,
    'events': CasesEvent,
    'alerts': Alert,
    'ioc_type': IocType
}


def get_iocs(case_identifier) -> list[Ioc]:
    return Ioc.query.filter(
        Ioc.case_id == case_identifier
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


def delete_ioc(ioc: Ioc):
    com_ids = IocComments.query.with_entities(
        IocComments.comment_id
    ).filter(
        IocComments.comment_ioc_id == ioc.ioc_id,
    ).all()

    com_ids = [c.comment_id for c in com_ids]
    IocComments.query.filter(IocComments.comment_id.in_(com_ids)).delete()
    Comments.query.filter(Comments.comment_id.in_(com_ids)).delete()

    db.session.delete(ioc)

    update_ioc_state(ioc.case_id)


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
     .outerjoin(Ioc.tlp)
     .order_by(IocType.type_name).all())

    return detailed_iocs


def get_ioc_links(ioc_id, user_search_limitations):
    if user_search_limitations:
        search_condition = and_(Cases.case_id.in_(user_search_limitations))
    else:
        search_condition = and_(Cases.case_id.in_([]))

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


def add_ioc(ioc: Ioc, user_id, caseid):
    ioc.user_id = user_id
    ioc.case_id = caseid
    db.session.add(ioc)

    update_ioc_state(caseid=caseid)
    add_obj_history_entry(ioc, 'created ioc')
    db.session.commit()


def case_iocs_db_exists(ioc: Ioc):
    iocs = Ioc.query.filter(Ioc.case_id == ioc.case_id,
                            Ioc.ioc_value == ioc.ioc_value,
                            Ioc.ioc_type_id == ioc.ioc_type_id)
    return iocs.first() is not None


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


def add_ioc_type(name: str, description: str, taxonomy: str):
    ioct = IocType(type_name=name,
                   type_description=description,
                   type_taxonomy=taxonomy
                )

    db_create(ioct)
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
        tlpDict[tlp.tlp_name] = tlp.tlp_id
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

    db_create(ec)


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
        Comments.comment_user_id,
        Comments.comment_case_id,
        User.name,
        User.user
    ).join(IocComments.comment)
            .join(Comments.user).first())


def delete_ioc_comment(user_identifier, ioc_id, comment_id):
    comment = Comments.query.filter(
        Comments.comment_id == comment_id,
        Comments.comment_user_id == user_identifier
    ).first()
    if not comment:
        return False, "You are not allowed to delete this comment"

    IocComments.query.filter(
        IocComments.comment_ioc_id == ioc_id,
        IocComments.comment_id == comment_id
    ).delete()

    db_delete(comment)

    return True, "Comment deleted"


def get_ioc_by_value(ioc_value, caseid=None):
    if caseid:
        Ioc.query.filter(Ioc.ioc_value == ioc_value, Ioc.case_id == caseid).first()

    return Ioc.query.filter(Ioc.ioc_value == ioc_value).first()


def get_filtered_iocs(
        caseid: int = None,
        pagination_parameters: PaginationParameters = None,
        request_parameters: dict = None
    ):
    """
    Get a list of iocs from the database, filtered by the given parameters
    """

    base_filter = Ioc.case_id == caseid if caseid is not None else None
    return get_filtered_data(Ioc, base_filter, pagination_parameters, request_parameters, relationship_model_map)


def search_iocs(search_value):
    search_condition = and_()
    res = Ioc.query.with_entities(
        Ioc.ioc_value.label('ioc_name'),
        Ioc.ioc_description.label('ioc_description'),
        Ioc.ioc_misp,
        IocType.type_name,
        Tlp.tlp_name,
        Tlp.tlp_bscolor,
        Cases.name.label('case_name'),
        Cases.case_id,
        Client.name.label('customer_name')
    ).filter(
        and_(
            Ioc.ioc_value.like(search_value),
            Ioc.case_id == Cases.case_id,
            Client.client_id == Cases.client_id,
            Ioc.ioc_tlp_id == Tlp.tlp_id,
            search_condition
        )
    ).join(Ioc.ioc_type).all()

    return [row._asdict() for row in res]
