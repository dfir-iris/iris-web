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

"""Business layer for the modules ("plugins") admin surface.

Wraps `app.datamgmt.iris_engine.modules_db` and `module_handler` so the
v2 REST layer can stay thin (parse args → call business → marshal). All
side-effecting calls raise `BusinessProcessingError` / `ObjectNotFoundError`
on failure so the route layer doesn't need to inspect tuple returns.
"""

import json

from app.datamgmt.iris_engine.modules_db import delete_module_from_id
from app.datamgmt.iris_engine.modules_db import get_module_config_from_id
from app.datamgmt.iris_engine.modules_db import get_module_from_id
from app.datamgmt.iris_engine.modules_db import iris_module_disable_by_id
from app.datamgmt.iris_engine.modules_db import iris_module_enable_by_id
from app.datamgmt.iris_engine.modules_db import iris_module_name_from_id
from app.datamgmt.iris_engine.modules_db import iris_module_save_parameter
from app.datamgmt.iris_engine.modules_db import iris_modules_list
from app.datamgmt.iris_engine.modules_db import module_list_hooks_view
from app.iris_engine.module_handler.module_handler import check_module_health
from app.iris_engine.module_handler.module_handler import instantiate_module_from_name
from app.iris_engine.module_handler.module_handler import iris_update_hooks
from app.iris_engine.module_handler.module_handler import register_module
from app.iris_engine.utils.tracker import track_activity
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


def _module_row_projection(row):
    return {
        'id': row['id'],
        'module_human_name': row['module_human_name'],
        'has_pipeline': row['has_pipeline'],
        'module_version': row['module_version'],
        'interface_version': row['interface_version'],
        'date_added': row['date_added'].isoformat() if row['date_added'] else None,
        'added_by': row['name'],
        'is_active': row['is_active'],
        'configured': row['configured'],
    }


def modules_list(page=1, per_page=25):
    """Return the projection used by the admin list page, paginated.

    The legacy underlying call (`iris_modules_list`) materialises every
    row and post-processes them (auto-disable misconfigured modules),
    which keeps the behaviour intact. Pagination is done in-memory
    afterwards — module fleets stay small (dozens at most), so a full
    scan is cheap and we avoid duplicating the auto-disable logic in a
    SQL paginate path.
    """
    rows = [_module_row_projection(r) for r in iris_modules_list()]
    total = len(rows)
    per_page = max(1, min(per_page, 200))
    page = max(1, page)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = rows[start:end]
    last_page = max(1, (total + per_page - 1) // per_page) if total else 1
    next_page = page + 1 if end < total else None
    return {
        'total': total,
        'data': page_items,
        'last_page': last_page,
        'current_page': page,
        'next_page': next_page,
    }


def modules_get(module_id):
    module = get_module_from_id(module_id)
    if module is None:
        raise ObjectNotFoundError()
    return module


def module_get_detail(module_id):
    """Read-only projection for the module-info modal.

    Returns the same metadata as the list endpoint plus the full
    configuration array (so the UI can render Section / Parameter /
    Value / Mandatory rows) and the module's description + target
    package — those are the bits the modal shows above the config table.
    """
    module = modules_get(module_id)
    return {
        'id': module.id,
        'module_name': module.module_name,
        'module_human_name': module.module_human_name,
        'module_description': module.module_description,
        'module_version': module.module_version,
        'interface_version': module.interface_version,
        'date_added': module.date_added.isoformat() if module.date_added else None,
        'is_active': module.is_active,
        'has_pipeline': module.has_pipeline,
        'module_type': module.module_type,
        'module_config': module.module_config or [],
    }


def modules_add(module_name):
    """Install + register a new module by its pip package name.

    Three stages mirror the legacy flow:
      1. import + instantiate the python class,
      2. health-check (interface contract),
      3. persist into `IrisModule` (this is what triggers default-value
         preset for every declared parameter).
    """
    if not module_name:
        raise BusinessProcessingError('Module name is required')

    class_, logs = instantiate_module_from_name(module_name)
    if not class_:
        raise BusinessProcessingError('Cannot import module', data=logs)

    is_ready, logs = check_module_health(class_)
    if not is_ready:
        raise BusinessProcessingError(
            "Module health check didn't pass. Please check logs.",
            data=logs,
        )

    module, message = register_module(module_name)
    if module is None:
        track_activity(
            f'addition of IRIS module {module_name} was attempted and failed',
            ctx_less=True,
        )
        raise BusinessProcessingError(f'Unable to register module: {message}')

    track_activity(f'IRIS module {module_name} was added', ctx_less=True)
    return module


def modules_delete(module_id):
    module = modules_get(module_id)
    delete_module_from_id(module.id)
    track_activity(f'IRIS module #{module.id} deleted', ctx_less=True)


def modules_enable(module_id):
    """Activate a module and resync its hooks.

    Re-syncing hooks on enable matters: the module may have been disabled
    long enough for its declared hooks to drift from what's in the DB
    (e.g. an upgrade added new hooks). Without the resync, calling them
    later would silently no-op.
    """
    module_name = iris_module_name_from_id(module_id)
    if module_name is None:
        raise ObjectNotFoundError()

    if not iris_module_enable_by_id(module_id):
        raise BusinessProcessingError('Unable to enable module')

    success, logs = iris_update_hooks(module_name, module_id)
    if not success:
        raise BusinessProcessingError('Unable to update hooks when enabling module', data=logs)

    track_activity(f'IRIS module ({module_name}) #{module_id} enabled', ctx_less=True)
    return logs


def modules_disable(module_id):
    if not iris_module_disable_by_id(module_id):
        raise BusinessProcessingError('Unable to disable module')

    track_activity(f'IRIS module #{module_id} disabled', ctx_less=True)


def modules_set_parameter(module_id, param_name, value):
    """Update a single parameter value on a module's config.

    Returns the refreshed module-detail projection so the UI can swap its
    in-memory copy without a second GET. Re-runs `iris_update_hooks` to
    pick up any hook changes that depended on the new value.
    """
    mod_config, mod_human_name, mod_name = get_module_config_from_id(module_id)
    if mod_config is None:
        raise ObjectNotFoundError()

    if not any(p.get('param_name') == param_name for p in mod_config):
        raise BusinessProcessingError(f'Unknown parameter: {param_name}')

    if not iris_module_save_parameter(module_id, mod_config, param_name, value):
        raise BusinessProcessingError('Unable to save parameter')

    track_activity(
        f'parameter {param_name} of mod ({mod_human_name}) #{module_id} was updated',
        ctx_less=True,
    )

    success, logs = iris_update_hooks(mod_name, module_id)
    if not success:
        raise BusinessProcessingError('Unable to update hooks', data=logs)

    return module_get_detail(module_id)


def modules_export_config(module_id):
    mod_config, mod_human_name, mod_name = get_module_config_from_id(module_id)
    if mod_config is None:
        raise ObjectNotFoundError()

    return {
        'module_name': mod_name,
        'module_human_name': mod_human_name,
        'module_configuration': mod_config,
    }


def modules_import_config(module_id, payload):
    """Bulk-apply a configuration dict to an existing module.

    Accepts either a list of `{param_name, value}` entries or a JSON
    string that decodes to one (legacy behaviour — the old form upload
    posted the raw file contents as a string).

    Skips unknown parameters silently and returns the list of skipped
    names so the caller can warn the user. Unknown params are treated as
    "module was downgraded" rather than as a hard error: the rest of the
    config still applies cleanly.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            raise BusinessProcessingError('Invalid data', data='Not a JSON file')

    if not isinstance(payload, list):
        raise BusinessProcessingError('Invalid data', data='Expected a list of parameters')

    mod_config, _, _ = get_module_config_from_id(module_id)
    if mod_config is None:
        raise ObjectNotFoundError()

    skipped = []
    for param in payload:
        param_name = param.get('param_name')
        value = param.get('value')
        if param_name is None:
            continue
        if not iris_module_save_parameter(module_id, mod_config, param_name, value):
            skipped.append(param_name)

    track_activity(
        f'parameters of mod #{module_id} were updated from config file',
        ctx_less=True,
    )

    return {
        'skipped': skipped,
        'module': module_get_detail(module_id),
    }


def modules_hooks_list(page=1, per_page=25):
    """Paginated list of every (module, hook) binding for the Hooks table.

    Same in-memory pagination as `modules_list` — hook counts grow with
    `n_modules * n_hooks_per_module` but remain bounded by the size of
    the deployment. Materialising the full set per request stays cheap
    even when the UI paginates.
    """
    rows = [
        {
            'id': row.id,
            'module_name': row.module_name,
            'is_active': row.is_active,
            'hook_name': row.hook_name,
            'hook_description': row.hook_description,
            'is_manual_hook': row.is_manual_hook,
        }
        for row in module_list_hooks_view()
    ]
    total = len(rows)
    per_page = max(1, min(per_page, 200))
    page = max(1, page)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = rows[start:end]
    last_page = max(1, (total + per_page - 1) // per_page) if total else 1
    next_page = page + 1 if end < total else None
    return {
        'total': total,
        'data': page_items,
        'last_page': last_page,
        'current_page': page,
        'next_page': next_page,
    }
