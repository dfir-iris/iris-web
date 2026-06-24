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

"""v2 endpoints for server-wide settings + the DB backup trigger.

Layout mirrors the rest of the v2 manage surface: a single
`ServerOperations` class, thin routes that delegate.

`PUT /server/settings` accepts a partial body — only the fields the
admin actually changed need to be sent. The full row is returned on
success so the UI can refresh in one round-trip.

`POST /server/backups/db` is the v2 replacement for the legacy GET
`/manage/server/backups/make-db`. The legacy GET stays for any
external automation calling it today; the v2 route is POST because
backup is a side-effecting action that shouldn't ride on GET.
"""

import marshmallow
from flask import Blueprint
from flask import Response
from flask import request

from app import app
from app import celery
from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.datamgmt.manage.manage_srv_settings_db import get_server_settings_as_dict
from app.datamgmt.manage.manage_srv_settings_db import get_srv_settings
from app.db import db
from app.iris_engine.backup.backup import backup_iris_db
from app.iris_engine.updater.updater import remove_periodic_update_checks
from app.iris_engine.updater.updater import setup_periodic_update_checks
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import Permissions
from app.schema.marshables import ServerSettingsSchema
from dictdiffer import diff


class ServerOperations:
    def __init__(self):
        self._schema = ServerSettingsSchema()

    # ----- Authentication ------------------------------------------

    @staticmethod
    def get_authentication_settings():
        try:
            auth_requirements = {
                "oidc_enabled": app.config.get("AUTHENTICATION_TYPE") == "oidc",
                "mfa_enabled": app.config.get("MFA_ENABLED"),
            }
            return response_api_success(auth_requirements)
        except Exception as e:
            return response_api_error("Data error", data=str(e))

    # ----- Server settings ----------------------------------------

    def read_settings(self) -> Response:
        """Return the full settings row + a small `versions` block.

        The version block isn't on `ServerSettings`; it's read straight
        from `app.config` + the alembic head. Bundling the two lets the
        page render its read-only top-of-page strip without a second
        round-trip.
        """
        settings = get_srv_settings()
        from app.datamgmt.manage.manage_srv_settings_db import get_alembic_revision

        return response_api_success({
            'settings': self._schema.dump(settings),
            'versions': {
                'iris_version': app.config.get('IRIS_VERSION'),
                'api_min': app.config.get('API_MIN_VERSION'),
                'api_max': app.config.get('API_MAX_VERSION'),
                'module_interface_min': app.config.get('MODULES_INTERFACE_MIN_VERSION'),
                'module_interface_max': app.config.get('MODULES_INTERFACE_MAX_VERSION'),
                'db_revision': get_alembic_revision(),
            },
        })

    def update_settings(self) -> Response:
        """Partial-update the singleton settings row.

        The schema is loaded with `partial=True` so the admin can send
        only the fields they changed. We compute a diff against the
        pre-update dump so the activity-log entry mentions exactly
        which keys moved — useful when chasing "who turned off MFA?".
        Mirrors the legacy `/manage/settings/update` behaviour 1:1
        (including the periodic-update-check side effect when the
        `enable_updates_check` flag flips).
        """
        if not request.is_json:
            return response_api_error('Invalid request')

        body = request.get_json() or {}
        settings = get_srv_settings()
        original_update_check = settings.enable_updates_check

        try:
            original_dump = self._schema.dump(settings)
            differences = list(diff(original_dump, body))
            changes = [
                {d[1]: d[2]} for d in differences if d[0] == 'change'
            ]
            updated = self._schema.load(body, instance=settings, partial=True)
            db.session.commit()

            # Periodic update-check Celery task is added/removed only
            # when the toggle actually flips. Reading the cached value
            # *before* the load+commit is critical — `updated` is the
            # same instance as `settings`, so its attribute is already
            # the new value once load() returns.
            if original_update_check != updated.enable_updates_check:
                if updated.enable_updates_check:
                    setup_periodic_update_checks(celery)
                else:
                    remove_periodic_update_checks()

            track_activity(f'Server settings updated: {changes}', ctx_less=True)
            # Re-cache the dump on app.config so other code paths that
            # read `app.config['SERVER_SETTINGS']` see the new values
            # without an extra DB hit. The legacy route did the same.
            app.config['SERVER_SETTINGS'] = self._schema.dump(updated)
            return response_api_success(app.config['SERVER_SETTINGS'])

        except marshmallow.exceptions.ValidationError as exc:
            return response_api_error('Data error', data=exc.messages)

    # ----- Database backup -----------------------------------------

    @staticmethod
    def make_db_backup() -> Response:
        """Trigger a synchronous Postgres dump.

        Returns the log lines from the dump runner on success so the
        admin can see what got backed up where. On failure the same
        log lines come back as `data` on the error envelope.
        """
        has_error, logs = backup_iris_db()
        if has_error:
            return response_api_error('Backup failed', data=logs)
        return response_api_success({'logs': logs})


server_blueprint = Blueprint("server_rest_v2", __name__, url_prefix="/server")

server_operations = ServerOperations()


@server_blueprint.get("/authentication-settings")
def server_get_authsettings() -> Response:
    return server_operations.get_authentication_settings()


@server_blueprint.get('/settings')
@ac_api_requires(Permissions.server_administrator)
def server_get_settings() -> Response:
    return server_operations.read_settings()


@server_blueprint.put('/settings')
@ac_api_requires(Permissions.server_administrator)
def server_put_settings() -> Response:
    return server_operations.update_settings()


@server_blueprint.post('/backups/db')
@ac_api_requires(Permissions.server_administrator)
def server_make_db_backup() -> Response:
    return server_operations.make_db_backup()


# Silence the unused-import linter — `get_server_settings_as_dict` is
# re-exported here so any future v2 route that needs the cached dict
# (rather than the ORM row) finds it under the conventional name.
_ = get_server_settings_as_dict
