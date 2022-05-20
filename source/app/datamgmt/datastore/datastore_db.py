#!/usr/bin/env python3
#
#
#  IRIS Source Code
#  Copyright (C) 2022 - DFIR IRIS Team
#  contact@dfir-iris.org
#  Created by whitekernel - 2022-05-17
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
from pathlib import Path

from sqlalchemy import and_

from app import app
from app import db
from app.models import DataStoreFile
from app.models import DataStorePath


def ds_list_tree(cid):
    dsp_root = DataStorePath.query.filter(
        and_(DataStorePath.path_case_id == cid,
             DataStorePath.path_is_root == True
             )
    ).first()

    if dsp_root is None:
        init_ds_tree(cid)

        dsp_root = DataStorePath.query.filter(
            and_(DataStorePath.path_case_id == cid,
                 DataStorePath.path_is_root == True
                 )
        ).first()

    dsp = DataStorePath.query.filter(
        and_(DataStorePath.path_case_id == cid,
             DataStorePath.path_is_root == False
             )
    ).order_by(
        DataStorePath.path_parent_id
    ).all()

    dsf = DataStoreFile.query.filter(
        DataStoreFile.file_case_id == cid
    ).all()

    dsp_root = dsp_root
    droot_id = f"d-{dsp_root.path_id}"

    path_tree = {
        droot_id: {
            "name": dsp_root.path_name,
            "type": "directory",
            "is_root": True,
            "children": {}
        }
    }

    droot_children = path_tree[droot_id]["children"]

    files_nodes = {}

    for dfile in dsf:
        dfnode = dfile.__dict__
        dfnode.pop('_sa_instance_state')
        dfnode['type'] = "file"
        dnode_id = f"f-{dfile.file_id}"
        dnode_parent_id = f"d-{dfile.file_parent_id}"

        if dnode_parent_id == droot_id:
            droot_children.update({
                dnode_id: dfnode
            })

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


def init_ds_tree(cid):
    dsp_root = DataStorePath.query.filter(
        and_(DataStorePath.path_case_id == cid,
             DataStorePath.path_is_root == True
             )
    ).all()

    if dsp_root:
      return dsp_root

    dsp_root = DataStorePath()
    dsp_root.path_name = f'Case {cid}'
    dsp_root.path_is_root = True
    dsp_root.path_case_id = cid
    dsp_root.path_parent_id = 0

    db.session.add(dsp_root)
    db.session.commit()

    for path in ['Evidences', 'IOCs', 'Images']:
        dsp_init = DataStorePath()
        dsp_init.path_parent_id = dsp_root.path_id
        dsp_init.path_case_id = cid
        dsp_init.path_name = path
        dsp_init.path_is_root = False
        db.session.add(dsp_init)

    db.session.commit()
    return dsp_root


def datastore_iter_tree(path_parent_id, path_node, tree):
    for parent_id, node in tree.items():
        if parent_id == path_parent_id:
            node["children"].update(path_node)
            return tree

        if isinstance(node, dict):
            datastore_iter_tree(path_parent_id, path_node, node)

    return None


def datastore_add_child_node(parent_node, folder_name, cid):
    try:

        dsp_base = DataStorePath.query.filter(
            DataStorePath.path_id == parent_node,
            DataStorePath.path_case_id == cid
        ).first()

    except Exception as e:
        return True, f'Unable to request datastore for parent node : {parent_node}'

    if dsp_base is None:
        return True, 'Parent node is invalid for this case'

    dsp = DataStorePath()
    dsp.path_case_id = cid
    dsp.path_name = folder_name
    dsp.path_parent_id = parent_node
    dsp.path_is_root = False

    db.session.add(dsp)
    db.session.commit()

    return False, 'Folder added'


def datastore_rename_node(parent_node, folder_name, cid):
    try:

        dsp_base = DataStorePath.query.filter(
            DataStorePath.path_id == parent_node,
            DataStorePath.path_case_id == cid
        ).first()

    except Exception as e:
        return True, f'Unable to request datastore for parent node : {parent_node}'

    if dsp_base is None:
        return True, 'Parent node is invalid for this case'

    dsp_base.path_name = folder_name
    db.session.commit()

    return False, 'Folder renamed'


def datastore_delete_node(node_id, cid):
    try:

        dsp_base = DataStorePath.query.filter(
            DataStorePath.path_id == node_id,
            DataStorePath.path_case_id == cid
        ).first()

    except Exception as e:
        return True, f'Unable to request datastore for parent node : {node_id}'

    datastore_iter_deletion(dsp_base, cid)

    return False, 'Folder and children deleted'


def datastore_iter_deletion(dsp, cid):
    dsp_children = DataStorePath.query.filter(
        and_(DataStorePath.path_case_id == cid,
             DataStorePath.path_is_root == False,
             DataStorePath.path_parent_id == dsp.path_id
             )
    ).all()
    for dsp_child in dsp_children:
        datastore_iter_deletion(dsp_child, cid)

    datastore_delete_files_of_path(dsp.path_id, cid)

    db.session.delete(dsp)
    db.session.commit()

    return None


def datastore_delete_files_of_path(node_id, cid):
    DataStoreFile.query.filter(
        and_(DataStoreFile.file_parent_id == node_id,
             DataStoreFile.file_case_id == cid
             )
    ).delete()

    return


def datastore_get_path_node(node_id, cid):
    return DataStorePath.query.filter(
        DataStorePath.path_id == node_id,
        DataStorePath.path_case_id == cid
    ).first()


def datastore_get_standard_path(datastore_file, cid):
    root_path = Path(app.config['DATASTORE_PATH']) / cid

    if datastore_file.file_is_ioc:
        target_path = root_path / 'IOCs'
    elif datastore_file.file_is_evidence:
        target_path = root_path / 'Evidences'
    else:
        target_path = root_path / 'Regulars'

    if not target_path.is_dir():
        root_path.mkdir(parents=True, exist_ok=True)

    return root_path / datastore_file.file_id
