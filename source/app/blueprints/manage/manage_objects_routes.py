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

# IMPORTS ------------------------------------------------
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import url_for

from app.forms import AddAssetForm
from app.models.authorization import Permissions
from app.util import ac_requires

manage_objects_blueprint = Blueprint('manage_objects',
                                          __name__,
                                          template_folder='templates')


# CONTENT ------------------------------------------------
@manage_objects_blueprint.route('/manage/objects')
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def manage_objects(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_objects.manage_objects', cid=caseid))

    form = AddAssetForm()

    # Return default page of case management
    return render_template('manage_objects.html', form=form)

