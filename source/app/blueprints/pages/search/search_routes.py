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
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from app.forms import SearchForm
from app.models.authorization import Permissions
from app.blueprints.access_controls import ac_requires

search_blueprint = Blueprint('search',
                             __name__,
                             template_folder='templates')


@search_blueprint.route('/search', methods=['GET'])
@ac_requires(Permissions.search_across_cases)
def search_file_get(caseid, url_redir):
    if url_redir:
        return redirect(url_for('search.search_file_get', cid=caseid))

    form = SearchForm(request.form)
    return render_template('search.html', form=form)
