#!/usr/bin/env python3
#
#  IRIS Source Code
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
from flask import Blueprint, Response

from app.datamgmt.manage.manage_case_classifications_db import get_case_classifications_list
from app.util import ac_api_requires
from app.util import response_success

manage_case_classification_blueprint = Blueprint('manage_case_classifications',
                                                 __name__,
                                                 template_folder='templates')


# CONTENT ------------------------------------------------
@manage_case_classification_blueprint.route('/manage/case-classifications/list', methods=['GET'])
@ac_api_requires()
def list_case_classifications(caseid: int) -> Response:
    """Get the list of case classifications

    Args:
        caseid (int): case id

    Returns:
        Flask Response object

    """
    l_cl = get_case_classifications_list()

    return response_success("", data=l_cl)

