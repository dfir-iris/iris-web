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

from app.models import DataStoreFile
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

    dsf = DataStoreFile.query.filter(
        DataStoreFile.data_case_id == cid
    ).all()

    if not dsp_root:
        return {}

    dsp_root = dsp_root[0]
    droot_id = f"d-{dsp_root.path_id}"

    path_tree = {
        droot_id: {
            "name": dsp_root.path_name,
            "type": "directory",
            "children": {}
        }
    }

    droot_children = path_tree[droot_id]["children"]

    files_nodes = {}

    for dfile in dsf:
        dfnode = dfile.__dict__
        dfnode.pop('_sa_instance_state')
        dfnode['type'] = "file"
        dnode_id = f"f-{dfile.data_id}"
        dnode_parent_id = f"d-{dfile.data_parent_id}"

        if dnode_parent_id == droot_id:
            droot_children.update(dfnode)

        elif dnode_parent_id in files_nodes:
            files_nodes[dnode_parent_id].update({
                dnode_id: dfnode
            })

        else:
            files_nodes[dnode_parent_id] = {dnode_id: dfnode}

    for dpath in dsp:
        dpath_id = f"d-{dpath.path_id}"
        dpath_parent_id = f"d-{dpath.path_parent_id}"
        path_node = {
            dpath_id: {
                "name": dpath.path_name,
                "type": "directory",
                "children": {}
            }
        }

        path_node_files = files_nodes.get(dpath_id)
        if path_node_files:
            path_node[dpath_id]["children"].update(path_node_files)

        if dpath_parent_id == droot_id:
            droot_children.update(path_node)

        else:
            datastore_iter_tree(dpath_parent_id, path_node, droot_children)

    return path_tree


def datastore_iter_tree(path_parent_id, path_node, tree):
    for parent_id, node in tree.items():
        if parent_id == path_parent_id:
            node["children"].update(path_node)
            return tree

        if isinstance(node, dict):
            datastore_iter_tree(path_parent_id, path_node, node)

    return None