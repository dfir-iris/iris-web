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

from flask import Blueprint, request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_success
from app.datamgmt.dashboard.dashboard_db import list_user_cases, list_user_tasks, list_user_reviews
from app.schema.marshables import CaseDetailsSchema, CaseTaskSchema, CaseSchema

dashboard_blueprint = Blueprint('dashboard',
                                __name__,
                                url_prefix='/dashboard')


# TODO this endpoint does not adhere to the conventions (verb in URL).
#      Prefer to use GET /api/v2/cases. Check it is possible. If not, evolve /api/v2/cases
#@dashboard_blueprint.route('/cases/list', methods=['GET'])
@ac_api_requires()
def list_own_cases():
    cases = list_user_cases(
        request.args.get('show_closed', 'false', type=str).lower() == 'true'
    )

    return response_api_success(data=CaseDetailsSchema(many=True).dump(cases))


# TODO this endpoint does not adhere to the conventions (verb in URL).
#      We should rather have /api/v2/tasks?
#@dashboard_blueprint.route('/tasks/list', methods=['GET'])
@ac_api_requires()
def list_own_tasks():
    ct = list_user_tasks()
    return response_api_success(data=CaseTaskSchema(many=True).dump(ct))


# TODO this endpoint does not adhere to the conventions (verb in URL).
#      We should rather have /api/v2/reviews?
#@dashboard_blueprint.route('/reviews/list', methods=['GET'])
@ac_api_requires()
def list_own_reviews():
    reviews = list_user_reviews()
    return response_api_success(
        data=CaseSchema(
            many=True,
            only=["case_id", "case_name",
                  "review_status.status_name", "status_id"]
        ).dump(reviews))
