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

from flask import Blueprint
from flask import render_template
from flask import url_for
from flask_wtf import FlaskForm
from werkzeug.utils import redirect

from app import app
from app.datamgmt.manage.manage_srv_settings_db import get_alembic_revision
from app.datamgmt.manage.manage_srv_settings_db import get_srv_settings
from app.iris_engine.updater.updater import is_updates_available
from app.models.authorization import Permissions
from app.blueprints.access_controls import ac_requires

manage_srv_settings_blueprint = Blueprint(
    'manage_srv_settings_blueprint',
    __name__,
    template_folder='templates'
)


@manage_srv_settings_blueprint.route('/manage/server/make-update', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_update(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_srv_settings_blueprint.manage_settings', cid=caseid))

    # Return default page of case management
    return render_template('manage_make_update.html')


@manage_srv_settings_blueprint.route('/manage/server/check-updates/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_check_updates_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_srv_settings_blueprint.manage_settings', cid=caseid))

    has_updates, updates_content, _ = is_updates_available()

    # Return default page of case management
    return render_template('modal_server_updates.html', has_updates=has_updates, updates_content=updates_content)


@manage_srv_settings_blueprint.route('/manage/settings', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_settings(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_srv_settings_blueprint.manage_settings', cid=caseid))

    form = FlaskForm()

    server_settings = get_srv_settings()

    versions = {
        "iris_current": app.config.get('IRIS_VERSION'),
        "api_min": app.config.get('API_MIN_VERSION'),
        "api_current": app.config.get('API_MAX_VERSION'),
        "interface_min": app.config.get('MODULES_INTERFACE_MIN_VERSION'),
        "interface_current": app.config.get('MODULES_INTERFACE_MAX_VERSION'),
        "db_revision": get_alembic_revision()
    }

    # Return default page of case management
    return render_template('manage_srv_settings.html', form=form, settings=server_settings, versions=versions)
