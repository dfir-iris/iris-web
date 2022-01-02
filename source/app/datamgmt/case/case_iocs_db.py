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

from app.datamgmt.states import update_ioc_state
from app.models import IocAssetLink, Ioc, IocLink, Tlp, Cases, Client, IocType
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
        Ioc.ioc_type,
        Ioc.ioc_description,
        Ioc.ioc_tags,
        Ioc.ioc_misp,
        Tlp.tlp_name,
        Tlp.tlp_bscolor
    ).filter(
        IocLink.case_id == caseid
    ).join(IocLink.ioc, Ioc.tlp).order_by(Ioc.ioc_type).all()

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


def find_ioc(ioc_value, ioc_type):
    ioc = Ioc.query.filter(Ioc.ioc_value == ioc_value,
                           Ioc.ioc_type == ioc_type).first()

    return ioc


def add_ioc(ioc, user_id, caseid):
    if not ioc:
        return None, False

    ioc.user_id = user_id

    db_ioc = find_ioc(ioc.ioc_value, ioc.ioc_type)

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


def get_tlps():
    return [(tlp.tlp_id, tlp.tlp_name) for tlp in Tlp.query.all()]
