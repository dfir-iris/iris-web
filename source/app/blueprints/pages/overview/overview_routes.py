#  IRIS Source Code
#  DFIR-IRIS Team
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

from flask import Blueprint
from flask import render_template
from flask import url_for
from flask_wtf import FlaskForm
from werkzeug.utils import redirect

from app.blueprints.access_controls import ac_requires

overview_blueprint = Blueprint(
    'overview',
    __name__,
    template_folder='templates'
)


@overview_blueprint.route('/overview', methods=['GET'])
@ac_requires()
def get_overview(caseid, url_redir):
    """
    Return an overview of the cases
    """
    if url_redir:
        return redirect(url_for('index.index', cid=caseid, redirect=True))

    form = FlaskForm()

    return render_template('overview.html', caseid=caseid, form=form)
