#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS) - DFIR-IRIS Team
#  ir@cyberactionlab.net - contact@dfir-iris.org
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
from flask import url_for
from flask_wtf import FlaskForm

from app.datamgmt.case.case_db import get_case
from app.models.authorization import CaseAccessLevel
from app.blueprints.access_controls import ac_case_requires

case_graph_blueprint = Blueprint('case_graph',
                                 __name__,
                                 template_folder='templates')


@case_graph_blueprint.route('/case/graph', methods=['GET'])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def case_graph(caseid, url_redir):
    if url_redir:
        return redirect(url_for('case_graph.case_graph', cid=caseid, redirect=True))

    case = get_case(caseid)
    form = FlaskForm()

    return render_template("case_graph.html", case=case, form=form)
