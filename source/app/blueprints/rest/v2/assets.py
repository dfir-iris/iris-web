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

from flask import Blueprint

from app.blueprints.access_controls import ac_api_requires, ac_fast_check_current_user_has_case_access
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.v2.assets_routes.comments import assets_comments_blueprint
from app.business.assets import assets_delete
from app.business.assets import assets_get
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import CaseAssetsSchema
from app.blueprints.access_controls import ac_api_return_access_denied


class AssetsOperation:

    def __init__(self):
        self._schema = CaseAssetsSchema()

    def read(self, identifier):

        try:
            asset = assets_get(identifier)

            # perform authz check
            if not ac_fast_check_current_user_has_case_access(asset.case_id,
                                                              [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=asset.case_id)

            result = self._schema.dump(asset)
            return response_api_success(result)
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())

    def delete(self, identifier):
        try:
            asset = assets_get(identifier)

            # perform authz check
            if not ac_fast_check_current_user_has_case_access(asset.case_id, [CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=asset.case_id)

            assets_delete(asset)
            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())


assets_blueprint = Blueprint('assets_api_v2', __name__, url_prefix='/assets')
assets_blueprint.register_blueprint(assets_comments_blueprint)
assets_operations = AssetsOperation()


@assets_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_asset(identifier):
    return assets_operations.read(identifier)


@assets_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_asset(identifier):
    return assets_operations.delete(identifier)
