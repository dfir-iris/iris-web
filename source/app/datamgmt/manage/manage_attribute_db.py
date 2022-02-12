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

from sqlalchemy.orm.attributes import flag_modified

from app import db
from app.models import Ioc, CustomAttribute


def update_all_attributes(object_type):

    obj_list = []
    if object_type == 'ioc':
        obj_list = Ioc.query.all()

    ioc_attr = CustomAttribute.query.with_entities(
        CustomAttribute.attribute_content
    ).filter(
        CustomAttribute.attribute_for == 'ioc'
    ).first()

    target_attr = ioc_attr.attribute_content

    for obj in obj_list:
        for tab in target_attr:
            if obj.custom_attributes.get(tab) is None:
                flag_modified(obj, "custom_attributes")
                obj.custom_attributes[tab] = target_attr[tab]

            else:
                for element in target_attr[tab]:
                    if element not in obj.custom_attributes[tab]:
                        flag_modified(obj, "custom_attributes")
                        obj.custom_attributes[tab][element] = target_attr[tab][element]

                    else:
                        if obj.custom_attributes[tab][element]['type'] != target_attr[tab][element]['type']:
                            flag_modified(obj, "custom_attributes")
                            obj.custom_attributes[tab][element]['type'] = target_attr[tab][element]['type']

                        if obj.custom_attributes[tab][element]['mandatory'] != target_attr[tab][element]['mandatory']:
                            flag_modified(obj, "custom_attributes")
                            obj.custom_attributes[tab][element]['mandatory'] = target_attr[tab][element]['mandatory']

        # Commit will only be effective if we flagged a modification, reducing load on the DB
        db.session.commit()