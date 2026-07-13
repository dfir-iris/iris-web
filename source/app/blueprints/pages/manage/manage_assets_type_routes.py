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

import os

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import url_for

from app import app
from app.forms import AddAssetForm
from app.models.authorization import Permissions
from app.models.assets import AssetsType
from app.blueprints.access_controls import ac_requires
from app.blueprints.responses import response_error

manage_assets_type_blueprint = Blueprint('manage_assets_type',
                                         __name__,
                                         template_folder='templates')


def _list_graph_icons():
    """List the icons available in the graph assets directory so they can be reused.

    Default icons are regular files with a .png/.svg extension. Uploaded custom icons are
    stored under a random name (no extension) in the asset store path and symlinked into the
    graph directory, so they are detected via their symlink target.
    """
    graph_dir = os.path.join(app.config['APP_PATH'], app.config['ASSET_SHOW_PATH'].strip(os.path.sep))
    store_dir = os.path.abspath(app.config['ASSET_STORE_PATH'])
    allowed_ext = ('.png', '.svg')
    icons = []
    try:
        for fn in os.listdir(graph_dir):
            full = os.path.join(graph_dir, fn)
            if not os.path.isfile(full):
                continue
            lower = fn.lower()
            is_icon = lower.endswith(allowed_ext)
            if not is_icon and os.path.islink(full):
                # Custom uploaded icon: symlink (random name, no extension) into the store path
                try:
                    if os.path.abspath(os.path.realpath(full)).startswith(store_dir):
                        is_icon = True
                except OSError:
                    pass
            if is_icon:
                icons.append({
                    'name': fn,
                    'path': os.path.join(app.config['ASSET_SHOW_PATH'], fn),
                })
    except OSError:
        pass
    icons.sort(key=lambda i: i['name'].lower())
    return icons


@manage_assets_type_blueprint.route('/manage/asset-type/update/<int:cur_id>/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def view_assets_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_assets.manage_assets', cid=caseid))

    form = AddAssetForm()
    asset = AssetsType.query.filter(AssetsType.asset_id == cur_id).first()
    if not asset:
        return response_error("Invalid asset type ID")

    form.asset_name.render_kw = {'value': asset.asset_name}
    form.asset_description.render_kw = {'value': asset.asset_description}
    form.asset_icon_compromised.render_kw = {'value': asset.asset_icon_compromised}
    form.asset_icon_not_compromised.render_kw = {'value': asset.asset_icon_not_compromised}
    setattr(asset, 'asset_icon_compromised_path', os.path.join(app.config['ASSET_SHOW_PATH'], asset.asset_icon_compromised))
    setattr(asset, 'asset_icon_not_compromised_path', os.path.join(app.config['ASSET_SHOW_PATH'], asset.asset_icon_not_compromised))

    return render_template("modal_add_asset_type.html", form=form, assettype=asset, icons=_list_graph_icons())


@manage_assets_type_blueprint.route('/manage/asset-type/add/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def add_assets_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_assets.manage_assets', cid=caseid))
    form = AddAssetForm()

    return render_template("modal_add_asset_type.html", form=form, assettype=None, icons=_list_graph_icons())
