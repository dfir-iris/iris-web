#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

import marshmallow
from flask import Blueprint
from flask import request

from app.db import db
from app.datamgmt.case.case_iocs_db import get_ioc_types_list
from app.datamgmt.manage.manage_case_objs import search_ioc_type_by_name
from app.iris_engine.utils.tracker import track_activity
from app.models.iocs import Ioc
from app.models.models import IocType
from app.models.authorization import Permissions
from app.schema.marshables import IocTypeSchema
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.responses import response_error
from app.blueprints.responses import response_success

manage_ioc_type_rest_blueprint = Blueprint('manage_ioc_types_rest', __name__)


@manage_ioc_type_rest_blueprint.route('/manage/ioc-types/list', methods=['GET'])
@ac_api_requires()
def list_ioc_types():
    lstatus = get_ioc_types_list()

    return response_success("", data=lstatus)


@manage_ioc_type_rest_blueprint.route('/manage/ioc-types/<int:cur_id>', methods=['GET'])
@ac_api_requires()
def get_ioc_type(cur_id):

    ioc_type = IocType.query.filter(IocType.type_id == cur_id).first()
    if not ioc_type:
        return response_error(f"Invalid ioc type ID {cur_id}")

    return response_success("", data=ioc_type)


@manage_ioc_type_rest_blueprint.route('/manage/ioc-types/add', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def add_ioc_type_api():
    if not request.is_json:
        return response_error("Invalid request")

    ioct_schema = IocTypeSchema()

    try:

        ioct_sc = ioct_schema.load(request.get_json())
        db.session.add(ioct_sc)
        db.session.commit()

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    track_activity(f"Added ioc type {ioct_sc.type_name}", ctx_less=True)
    # Return the assets
    return response_success("Added successfully", data=ioct_sc)


@manage_ioc_type_rest_blueprint.route('/manage/ioc-types/delete/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def remove_ioc_type(cur_id):
    type_id = IocType.query.filter(
        IocType.type_id == cur_id
    ).first()

    is_referenced = Ioc.query.filter(Ioc.ioc_type_id == cur_id).first()
    if is_referenced:
        return response_error("Cannot delete a referenced ioc type. Please delete any ioc of this type first.")

    if type_id:
        db.session.delete(type_id)
        track_activity(f"Deleted ioc type ID {cur_id}", ctx_less=True)
        return response_success(f"Deleted ioc type ID {cur_id}")

    track_activity(f'Attempted to delete ioc type ID {cur_id}, but was not found', ctx_less=True)

    return response_error(f"Attempted to delete ioc type ID {cur_id}, but was not found")


@manage_ioc_type_rest_blueprint.route('/manage/ioc-types/update/<int:cur_id>', methods=['POST'])
@ac_api_requires(Permissions.server_administrator)
def update_ioc(cur_id):
    if not request.is_json:
        return response_error("Invalid request")

    ioc_type = IocType.query.filter(IocType.type_id == cur_id).first()
    if not ioc_type:
        return response_error(f"Invalid ioc type ID {cur_id}")

    ioct_schema = IocTypeSchema()

    try:

        ioct_sc = ioct_schema.load(request.get_json(), instance=ioc_type)

        if ioct_sc:
            track_activity(f"updated ioc type type {ioct_sc.type_name}")
            return response_success("IOC type updated", ioct_sc)

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.messages)

    return response_error("Unexpected error server-side. Nothing updated", data=ioc_type)


@manage_ioc_type_rest_blueprint.route('/manage/ioc-types/search', methods=['POST'])
@ac_api_requires()
def search_ioc_type():
    """Searches for IOC types in the database.

    This function searches for IOC types in the database with a name that contains the specified search term.
    It returns a JSON response containing the matching IOC types.

    Returns:
        A JSON response containing the matching IOC types.

    """
    if not request.is_json:
        return response_error("Invalid request")

    ioc_type = request.json.get('ioc_type')
    if ioc_type is None:
        return response_error("Invalid ioc type. Got None")

    exact_match = request.json.get('exact_match', False)

    # Search for IOC types with a name that contains the specified search term
    ioc_type = search_ioc_type_by_name(ioc_type, exact_match=exact_match)
    if not ioc_type:
        return response_error("No ioc types found")

    # Serialize the IOC types and return them in a JSON response
    ioct_schema = IocTypeSchema(many=True)
    return response_success("", data=ioct_schema.dump(ioc_type))
