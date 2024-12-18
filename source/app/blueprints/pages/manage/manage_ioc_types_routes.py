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
from werkzeug.utils import redirect

from app.forms import AddIocTypeForm
from app.models.models import IocType
from app.models.authorization import Permissions
from app.blueprints.access_controls import ac_requires
from app.blueprints.responses import response_error

manage_ioc_type_blueprint = Blueprint('manage_ioc_types',
                                      __name__,
                                      template_folder='templates')


@manage_ioc_type_blueprint.route('/manage/ioc-types/update/<int:cur_id>/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def view_ioc_modal(cur_id, caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_ioc_types.view_ioc_modal', cid=caseid))

    form = AddIocTypeForm()
    ioct = IocType.query.filter(IocType.type_id == cur_id).first()
    if not ioct:
        return response_error("Invalid asset type ID")

    form.type_name.render_kw = {'value': ioct.type_name}
    form.type_description.render_kw = {'value': ioct.type_description}
    form.type_taxonomy.data = ioct.type_taxonomy
    form.type_validation_regex.data = ioct.type_validation_regex
    form.type_validation_expect.data = ioct.type_validation_expect

    return render_template("modal_add_ioc_type.html", form=form, ioc_type=ioct)


@manage_ioc_type_blueprint.route('/manage/ioc-types/add/modal', methods=['GET'])
@ac_requires(Permissions.server_administrator, no_cid_required=True)
def add_ioc_modal(caseid, url_redir):
    if url_redir:
        return redirect(url_for('manage_ioc_types.view_ioc_modal', cid=caseid))

    form = AddIocTypeForm()

    return render_template("modal_add_ioc_type.html", form=form, ioc_type=None)
