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

from app.models import Tlp
from app.util import ac_api_requires
from app.util import response_error
from app.util import response_success

manage_tlp_type_blueprint = Blueprint('manage_tlp_types',
                                      __name__,
                                      template_folder='templates')


# CONTENT ------------------------------------------------
@manage_tlp_type_blueprint.route('/manage/tlp/list', methods=['GET'])
@ac_api_requires()
def list_tlp_types():
    lstatus = Tlp.query.all()

    return response_success("", data=lstatus)


@manage_tlp_type_blueprint.route('/manage/tlp/<int:cur_id>', methods=['GET'])
@ac_api_requires()
def get_tlp_type(cur_id):

    tlp_type = Tlp.query.filter(Tlp.tlp_id == cur_id).first()
    if not tlp_type:
        return response_error("Invalid TLP ID {type_id}".format(type_id=cur_id))

    return response_success("", data=tlp_type)


