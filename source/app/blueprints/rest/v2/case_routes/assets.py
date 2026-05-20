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
from flask import request
from marshmallow import ValidationError

from app.blueprints.access_controls import ac_api_requires, ac_fast_check_current_user_has_case_access
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.blueprints.rest.parsing import parse_fields_parameters
from app.business.cases import cases_exists
from app.business.assets import assets_create
from app.business.assets import assets_filter
from app.business.assets import assets_get
from app.business.assets import assets_update
from app.business.assets import assets_delete
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.iris_engine.module_handler.module_handler import call_deprecated_on_preload_modules_hook
from app.models.authorization import CaseAccessLevel
from app.schema.marshables import CaseAssetsSchema
from app.blueprints.iris_user import iris_current_user


class AssetsOperations:

    def __init__(self):
        self._schema = CaseAssetsSchema()

    @staticmethod
    def _get_asset_in_case(identifier, case_identifier):
        asset = assets_get(identifier)
        if asset.case_id != case_identifier:
            raise ObjectNotFoundError
        return asset

    def search(self, case_identifier):
        if not ac_fast_check_current_user_has_case_access(case_identifier,
                                                          [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        try:
            pagination_parameters = parse_pagination_parameters(request)
            fields = parse_fields_parameters(request)

            assets = assets_filter(case_identifier, pagination_parameters, request.args.to_dict())

            if fields:
                asset_schema = CaseAssetsSchema(only=fields)
            else:
                asset_schema = self._schema

            return response_api_paginated(asset_schema, assets)

        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())

    def create(self, case_identifier):
        if not cases_exists(case_identifier):
            return response_api_not_found()
        if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
            return ac_api_return_access_denied(caseid=case_identifier)

        try:
            request_data = call_deprecated_on_preload_modules_hook('asset_create', request.get_json(), case_identifier)
            ioc_links = request_data.get('ioc_links')
            asset = self._schema.load(request_data)
            create_asset = assets_create(iris_current_user, case_identifier, asset, ioc_links)
            return response_api_created(self._schema.dump(create_asset))

        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)
        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def read(self, case_identifier, identifier):
        try:
            asset = self._get_asset_in_case(identifier, case_identifier)

            if not ac_fast_check_current_user_has_case_access(asset.case_id,
                                                              [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=asset.case_id)

            return response_api_success(self._schema.dump(asset))
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())

    def update(self, case_identifier, identifier):
        try:
            asset = self._get_asset_in_case(identifier, case_identifier)

            if not ac_fast_check_current_user_has_case_access(asset.case_id, [CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=asset.case_id)

            request_data = call_deprecated_on_preload_modules_hook('asset_update', request.get_json(), case_identifier)

            request_data['asset_id'] = asset.asset_id
            loaded_asset = self._schema.load(request_data, instance=asset, partial=True)
            updated_asset = assets_update(loaded_asset)

            result = self._schema.dump(updated_asset)
            return response_api_success(result)

        except ValidationError as e:
            return response_api_error('Data error', data=e.messages)

        except ObjectNotFoundError:
            return response_api_not_found()

        except BusinessProcessingError as e:
            return response_api_error(e.get_message(), data=e.get_data())

    def delete(self, case_identifier, identifier):
        try:
            asset = self._get_asset_in_case(identifier, case_identifier)

            if not ac_fast_check_current_user_has_case_access(asset.case_id, [CaseAccessLevel.full_access]):
                return ac_api_return_access_denied(caseid=asset.case_id)

            assets_delete(asset)
            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())


assets_operations = AssetsOperations()
case_assets_blueprint = Blueprint('case_assets',
                                  __name__,
                                  url_prefix='/<int:case_identifier>/assets')


@case_assets_blueprint.get('')
@ac_api_requires()
def case_list_assets(case_identifier):
    return assets_operations.search(case_identifier)


@case_assets_blueprint.post('')
@ac_api_requires()
def add_asset(case_identifier):
    return assets_operations.create(case_identifier)


@case_assets_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_asset(case_identifier, identifier):
    return assets_operations.read(case_identifier, identifier)


@case_assets_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_asset(case_identifier, identifier):
    return assets_operations.update(case_identifier, identifier)


@case_assets_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_asset(case_identifier, identifier):
    return assets_operations.delete(case_identifier, identifier)
