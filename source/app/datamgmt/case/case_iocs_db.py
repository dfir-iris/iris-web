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
import json

from sqlalchemy import and_
from sqlalchemy.orm.attributes import flag_modified

from app.datamgmt.states import update_ioc_state
from app.models import IocAssetLink, Ioc, IocLink, Tlp, Cases, Client, IocType, CustomAttribute
from app import db


def get_iocs(caseid):
    iocs = IocLink.query.with_entities(
        Ioc.ioc_value,
        Ioc.ioc_id
    ).filter(
        IocLink.case_id == caseid,
        IocLink.ioc_id == Ioc.ioc_id
    ).all()

    return iocs


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

    IocLink.query.filter(
        and_(
            IocLink.ioc_id == ioc.ioc_id,
            IocLink.case_id == caseid
        )
    ).delete()
    db.session.commit()

    res = IocLink.query.filter(
            IocLink.ioc_id == ioc.ioc_id,
            ).all()

    if res:
        return False

    IocAssetLink.query.filter(
        IocAssetLink.ioc_id == ioc.ioc_id
    ).delete()

    db.session.delete(ioc)

    update_ioc_state(caseid=caseid)
    db.session.commit()

    return True


def get_detailed_iocs(caseid):
    detailed_iocs = IocLink.query.with_entities(
        Ioc.ioc_id,
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
    ).join(IocLink.ioc,
           Ioc.tlp,
           Ioc.ioc_type
    ).order_by(IocType.type_name).all()

    return detailed_iocs


def get_ioc_links(ioc_id, caseid):
    ioc_link = IocLink.query.with_entities(
        Cases.case_id,
        Cases.name.label('case_name'),
        Client.name.label('client_name')
    ).filter(
        IocLink.ioc_id == ioc_id,
        IocLink.case_id != caseid
    ).join(IocLink.case, Cases.client).all()

    return ioc_link


def find_ioc(ioc_value, ioc_type_id):
    ioc = Ioc.query.filter(Ioc.ioc_value == ioc_value,
                           Ioc.ioc_type_id == ioc_type_id).first()

    return ioc


def add_ioc(ioc, user_id, caseid):
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


def update_all_ioc_attributes():
    iocs = Ioc.query.all()

    ioc_attr = CustomAttribute.query.with_entities(
        CustomAttribute.attribute_content
    ).filter(
        CustomAttribute.attribute_for == 'ioc'
    ).first()

    target_attr = ioc_attr.attribute_content

    for ioc in iocs:
        for tab in target_attr:
            if ioc.custom_attributes.get(tab) is None:
                flag_modified(ioc, "custom_attributes")
                ioc.custom_attributes[tab] = target_attr[tab]

            else:
                for element in target_attr[tab]:
                    if element not in ioc.custom_attributes[tab]:
                        flag_modified(ioc, "custom_attributes")
                        ioc.custom_attributes[tab][element] = target_attr[tab][element]

                    else:
                        if ioc.custom_attributes[tab][element]['type'] != target_attr[tab][element]['type']:
                            flag_modified(ioc, "custom_attributes")
                            ioc.custom_attributes[tab][element]['type'] = target_attr[tab][element]['type']

                        if ioc.custom_attributes[tab][element]['mandatory'] != target_attr[tab][element]['mandatory']:
                            flag_modified(ioc, "custom_attributes")
                            ioc.custom_attributes[tab][element]['mandatory'] = target_attr[tab][element]['mandatory']

        # Commit will only be effective if we flagged a modification, reducing load on the DB
        db.session.commit()
