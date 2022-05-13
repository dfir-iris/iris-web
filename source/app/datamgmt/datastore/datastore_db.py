#!/usr/bin/env python3
#
#
#  IRIS Source Code
#  Copyright (C) 2022 - DFIR IRIS Team
#  contact@dfir-iris.org
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

from app.models import DataStorePath


def ds_list_tree(cid):
    dsp_root = DataStorePath.query.filter(
        and_(DataStorePath.path_case_id == cid,
             DataStorePath.path_is_root == True
             )
    ).all()

    dsp = DataStorePath.query.filter(
        and_(DataStorePath.path_case_id == cid,
             DataStorePath.path_is_root == False
             )
    ).order_by(
        DataStorePath.path_parent_id
    ).all()

    if not dsp_root:
        return {}

    dsp_root = dsp_root[0]

    path_tree = {
        dsp_root.path_id : {
            "name": dsp_root.path_name,
            "type": "directory",
            "children": {}
        }
    }

    droot_children = path_tree[dsp_root.path_id]["children"]

    for dpath in dsp:

        path_node = {
            dpath.path_id: {
                "name": dpath.path_name,
                "type": "directory",
                "children": {}
            }
        }

        if dpath.path_parent_id ==  dsp_root.path_id:
            droot_children.update(path_node)

        else:
            datastore_iter_tree(dpath.path_parent_id, path_node, droot_children)

    return path_tree


def datastore_iter_tree(path_parent_id, path_node, tree):
    for k, v in tree.items():
        if k == path_parent_id:
            v["children"].update(path_node)
            return tree

        if isinstance(v, dict):
            datastore_iter_tree(path_parent_id, path_node, v)

    return None