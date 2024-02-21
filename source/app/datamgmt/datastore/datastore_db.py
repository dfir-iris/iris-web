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

import datetime
from pathlib import Path

from flask_login import current_user
from sqlalchemy import and_
from sqlalchemy import func

from app import app
from app import db
from app.datamgmt.case.case_iocs_db import add_ioc_link
from app.models import CaseReceivedFile
from app.models import DataStoreFile
from app.models import DataStorePath
from app.models import Ioc
from app.models import IocType
from app.models import Tlp


def datastore_get_root(cid):
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

    return dsp_root

def ds_list_tree(cid):
    dsp_root = datastore_get_root(cid)

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
        return True, f'Unable to request datastore for parent node : {parent_node}', None

    if dsp_base is None:
        return True, 'Parent node is invalid for this case', None

    dsp = DataStorePath()
    dsp.path_case_id = cid
    dsp.path_name = folder_name
    dsp.path_parent_id = parent_node
    dsp.path_is_root = False

    db.session.add(dsp)
    db.session.commit()

    return False, 'Folder added', dsp


def datastore_rename_node(parent_node, folder_name, cid):
    try:

        dsp_base = DataStorePath.query.filter(
            DataStorePath.path_id == parent_node,
            DataStorePath.path_case_id == cid
        ).first()

    except Exception as e:
        return True, f'Unable to request datastore for parent node : {parent_node}', None

    if dsp_base is None:
        return True, 'Parent node is invalid for this case', None

    dsp_base.path_name = folder_name
    db.session.commit()

    return False, 'Folder renamed', dsp_base


def datastore_delete_node(node_id, cid):
    try:

        dsp_base = DataStorePath.query.filter(
            DataStorePath.path_id == node_id,
            DataStorePath.path_case_id == cid
        ).first()

    except Exception as e:
        return True, f'Unable to request datastore for parent node : {node_id}'

    if dsp_base is None:
        return True, 'Parent node is invalid for this case'

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
    dsf_list = DataStoreFile.query.filter(
        and_(DataStoreFile.file_parent_id == node_id,
             DataStoreFile.file_case_id == cid
             )
    ).all()

    for dsf_list_item in dsf_list:

        fln = Path(dsf_list_item.file_local_name)
        if fln.is_file():
            fln.unlink(missing_ok=True)

        db.session.delete(dsf_list_item)
        db.session.commit()

    return


def datastore_get_path_node(node_id, cid):
    return DataStorePath.query.filter(
        DataStorePath.path_id == node_id,
        DataStorePath.path_case_id == cid
    ).first()


def datastore_get_interactive_path_node(cid):
    dsp = DataStorePath.query.filter(
        DataStorePath.path_name == 'Notes Upload',
        DataStorePath.path_case_id == cid
    ).first()

    if not dsp:
        dsp_root = datastore_get_root(cid)
        dsp = DataStorePath()
        dsp.path_case_id = cid
        dsp.path_parent_id = dsp_root.path_id
        dsp.path_name = 'Notes Upload'
        dsp.path_is_root = False

        db.session.add(dsp)
        db.session.commit()

    return dsp


def datastore_get_standard_path(datastore_file, cid):
    root_path = Path(app.config['DATASTORE_PATH'])

    if datastore_file.file_is_ioc:
        target_path = root_path / 'IOCs'
    elif datastore_file.file_is_evidence:
        target_path = root_path / 'Evidences'
    else:
        target_path = root_path / 'Regulars'

    target_path = target_path / f"case-{cid}"

    if not target_path.is_dir():
        target_path.mkdir(parents=True, exist_ok=True)

    return target_path / f"dsf-{datastore_file.file_uuid}"


def datastore_get_file(file_id, cid):
    dsf = DataStoreFile.query.filter(
        DataStoreFile.file_id == file_id,
        DataStoreFile.file_case_id == cid
    ).first()

    return dsf


def datastore_delete_file(cur_id, cid):
    dsf = DataStoreFile.query.filter(
        DataStoreFile.file_id == cur_id,
        DataStoreFile.file_case_id == cid
    ).first()

    if dsf is None:
        return True, 'Invalid DS file ID for this case'

    fln = Path(dsf.file_local_name)
    if fln.is_file():
        fln.unlink(missing_ok=True)

    db.session.delete(dsf)
    db.session.commit()

    return False, f'File {cur_id} deleted'


def datastore_add_file_as_ioc(dsf, caseid):
    ioc = Ioc.query.filter(
        Ioc.ioc_value == dsf.file_sha256
    ).first()

    ioc_type_id = IocType.query.filter(
        IocType.type_name == 'sha256'
    ).first()

    ioc_tlp_id = Tlp.query.filter(
        Tlp.tlp_name == 'amber'
    ).first()

    if ioc is None:
        ioc = Ioc()
        ioc.ioc_value = dsf.file_sha256
        ioc.ioc_description = f"SHA256 of {dsf.file_original_name}. Imported from datastore."
        ioc.ioc_type_id = ioc_type_id.type_id
        ioc.ioc_tlp_id = ioc_tlp_id.tlp_id
        ioc.ioc_tags = "datastore"
        ioc.user_id = current_user.id

        db.session.add(ioc)
        db.session.commit()

    add_ioc_link(ioc.ioc_id, caseid)

    return


def datastore_add_file_as_evidence(dsf, caseid):
    crf = CaseReceivedFile.query.filter(
        CaseReceivedFile.file_hash == dsf.file_sha256
    ).first()

    if crf is None:
        crf = CaseReceivedFile()
        crf.file_hash = dsf.file_sha256
        crf.file_description = f"Imported from datastore. {dsf.file_description}"
        crf.case_id = caseid
        crf.date_added = datetime.datetime.now()
        crf.filename = dsf.file_original_name
        crf.file_size = dsf.file_size
        crf.user_id = current_user.id

        db.session.add(crf)
        db.session.commit()

    return


def datastore_get_local_file_path(file_id, caseid):
    dsf = DataStoreFile.query.filter(
        DataStoreFile.file_id == file_id,
        DataStoreFile.file_case_id == caseid
    ).first()

    if dsf is None:
        return True, 'Invalid DS file ID for this case'

    return False, dsf


def datastore_filter_tree(filter_d, caseid):
    names = filter_d.get('name')
    storage_names = filter_d.get('storage_name')
    tags = filter_d.get('tag')
    descriptions = filter_d.get('description')
    is_ioc = filter_d.get('is_ioc')
    is_evidence = filter_d.get('is_evidence')
    has_password = filter_d.get('has_password')
    file_id = filter_d.get('id')
    file_uuid = filter_d.get('uuid')
    file_sha256 = filter_d.get('sha256')

    condition = (DataStoreFile.file_case_id == caseid)
    if file_id:
        for fid in file_id:
            if fid:
                fid = fid.replace('dsf-', '')
                condition = and_(condition, DataStoreFile.file_id == fid)

    if file_uuid:
        for fuid in file_uuid:
            if fuid:
                fuid = fuid.replace('dsf-', '')
                condition = and_(condition, DataStoreFile.file_uuid == fuid)

    if file_sha256:
        for fsha in file_sha256:
            if fsha:
                condition = and_(condition, func.lower(DataStoreFile.file_sha256) == fsha.lower())

    if names:
        for name in names:
            condition = and_(condition,
                             DataStoreFile.file_original_name.ilike(f'%{name}%'))

    if storage_names:
        for name in storage_names:
            condition = and_(condition,
                            DataStoreFile.file_local_name.ilike(f'%{name}%'))

    if tags:
        for tag in tags:
            condition = and_(condition,
                             DataStoreFile.file_tags.ilike(f'%{tag}%'))

    if descriptions:
        for description in descriptions:
            condition = and_(condition,
                             DataStoreFile.file_description.ilike(f'%{description}%'))

    if is_ioc is not None:
        condition = and_(condition,
                         (DataStoreFile.file_is_ioc == True))

    if is_evidence is not None:
        condition = and_(condition,
                         (DataStoreFile.file_is_evidence == True))

    if has_password is not None:
        condition = and_(condition,
                         (DataStoreFile.file_password != ""))

    dsp_root = DataStorePath.query.filter(
        and_(DataStorePath.path_case_id == caseid,
             DataStorePath.path_is_root == True
             )
    ).first()

    if dsp_root is None:
        init_ds_tree(caseid)

        dsp_root = DataStorePath.query.filter(
            and_(DataStorePath.path_case_id == caseid,
                 DataStorePath.path_is_root == True
                 )
        ).first()

    dsp = DataStorePath.query.filter(
        and_(DataStorePath.path_case_id == caseid,
             DataStorePath.path_is_root == False
             )
    ).order_by(
        DataStorePath.path_parent_id
    ).all()

    try:
        dsf = DataStoreFile.query.filter(
            condition
        ).all()

    except Exception as e:
        return None, str(e)

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

    return path_tree, 'Success'

