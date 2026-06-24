#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
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

"""v2 REST endpoints for the modules ("plugins") admin page.

The list payload is intentionally small (a few dozen rows at most across
any real-world deployment) so there's no `page` / `per_page` here —
just a flat list. Add pagination if a deployment ever ships more than
~200 modules.
"""

from flask import Blueprint
from flask import request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.business.modules import module_get_detail
from app.business.modules import modules_add
from app.business.modules import modules_delete
from app.business.modules import modules_disable
from app.business.modules import modules_enable
from app.business.modules import modules_export_config
from app.business.modules import modules_hooks_list
from app.business.modules import modules_import_config
from app.business.modules import modules_list
from app.business.modules import modules_set_parameter
from app.models.authorization import Permissions
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


modules_blueprint = Blueprint('modules_rest_v2', __name__, url_prefix='/modules')


@modules_blueprint.get('')
@ac_api_requires(Permissions.server_administrator)
def list_modules():
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=25, type=int)
    return response_api_success(modules_list(page=page, per_page=per_page))


@modules_blueprint.post('')
@ac_api_requires(Permissions.server_administrator)
def add_module():
    request_data = request.get_json() or {}
    module_name = request_data.get('module_name')

    try:
        module = modules_add(module_name)
        return response_api_created(module_get_detail(module.id))
    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())


@modules_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def get_module(identifier):
    try:
        return response_api_success(module_get_detail(identifier))
    except ObjectNotFoundError:
        return response_api_not_found()


@modules_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.server_administrator)
def delete_module(identifier):
    try:
        modules_delete(identifier)
        return response_api_deleted()
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())


@modules_blueprint.post('/<int:identifier>/enable')
@ac_api_requires(Permissions.server_administrator)
def enable_module(identifier):
    try:
        modules_enable(identifier)
        return response_api_success(module_get_detail(identifier))
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())


@modules_blueprint.post('/<int:identifier>/disable')
@ac_api_requires(Permissions.server_administrator)
def disable_module(identifier):
    try:
        modules_disable(identifier)
        return response_api_success(module_get_detail(identifier))
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())


@modules_blueprint.put('/<int:identifier>/parameters/<path:param_name>')
@ac_api_requires(Permissions.server_administrator)
def set_module_parameter(identifier, param_name):
    """Update one parameter.

    The legacy API encoded `mod_id##param_name` as base64 in the URL —
    we don't carry that scheme over: the v2 URL puts `module_id` and
    `param_name` as discrete path segments. `path:` matches slashes so
    parameter names that contain `/` (rare but legal) round-trip cleanly.
    """
    request_data = request.get_json() or {}
    if 'parameter_value' not in request_data:
        return response_api_error('Missing field: parameter_value')

    try:
        return response_api_success(
            modules_set_parameter(identifier, param_name, request_data['parameter_value'])
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())


@modules_blueprint.get('/<int:identifier>/export-config')
@ac_api_requires(Permissions.server_administrator)
def export_module_config(identifier):
    try:
        return response_api_success(modules_export_config(identifier))
    except ObjectNotFoundError:
        return response_api_not_found()


@modules_blueprint.post('/<int:identifier>/import-config')
@ac_api_requires(Permissions.server_administrator)
def import_module_config(identifier):
    request_data = request.get_json() or {}
    payload = request_data.get('module_configuration')
    if payload is None:
        return response_api_error('Missing field: module_configuration')

    try:
        return response_api_success(modules_import_config(identifier, payload))
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message(), data=e.get_data())


@modules_blueprint.get('/hooks')
@ac_api_requires(Permissions.server_administrator)
def list_modules_hooks():
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=25, type=int)
    return response_api_success(modules_hooks_list(page=page, per_page=per_page))
